"""Trait extraction: included images + brand info -> Style DNA traits.

The model proposes traits and says which images show each one. Everything that can be
checked or counted is done here in code rather than taken on trust: evidence ids must be
images we actually sent, seen_count is counted from them, and low_confidence follows
from the confidence value.
"""

import json
import logging
from pathlib import Path
from typing import Callable, Optional

from pydantic import BaseModel, Field

from backend.ai_core.errors import AiCoreError
from backend.ai_core.images import ImageLoadError, LoadedImage, load_image
from backend.ai_core.providers import VisionProvider, get_provider
from contracts.models import Brand, Color, ExtractResponse, ImageCandidate, Trait

log = logging.getLogger(__name__)

PROMPT_FILE = Path(__file__).parent / "prompts" / "extract_traits.md"

MAX_IMAGES = 20             # most relevant first; keeps one request affordable
MIN_IMAGES = 2              # "recurring" needs at least two images
LOW_CONFIDENCE_BELOW = 0.6  # AGENTS.md


class ModelTrait(BaseModel):
    """One trait as the model is asked to return it (see prompts/extract_traits.md)."""

    name: str = Field(min_length=1)
    description: str
    evidence_image_ids: list[str]
    confidence: float = Field(ge=0, le=1)
    importance: int = Field(default=50, ge=0, le=100)


class ModelAnswer(BaseModel):
    traits: list[ModelTrait]
    tone_words: list[str] = []
    colors: list[Color] = []


def extract_dna(
    brand: Brand,
    candidates: list[ImageCandidate],
    ask: Optional[VisionProvider] = None,
    load: Optional[Callable[[str, str], LoadedImage]] = None,
) -> ExtractResponse:
    """`ask` and `load` can be replaced in tests, so no API key or network is needed."""
    ask = ask or get_provider()  # fail before downloading anything if no model is set up
    load = load or load_image

    included = [c for c in candidates if c.included]
    if not included:
        raise AiCoreError(
            "no_images_selected",
            "No images are selected — include at least 2 reference images before extracting.",
            status=422,
        )
    included.sort(key=lambda c: c.relevance or 0, reverse=True)
    included = included[:MAX_IMAGES]

    images = []
    for candidate in included:
        try:
            images.append(load(candidate.id, candidate.url))
        except ImageLoadError as problem:
            log.warning("Skipped %s (%s): %s", candidate.id, candidate.source_domain, problem)

    if len(images) < MIN_IMAGES:
        raise AiCoreError(
            "too_few_images",
            f"Only {len(images)} of the {len(included)} selected images could be loaded — "
            f"the AI needs at least {MIN_IMAGES} to find recurring traits. "
            "Try including more images or adding some by upload.",
            status=422,
        )

    answer = ask_for_answer(ask, build_prompt(brand, images), images)
    return to_response(answer, sent_ids=[image.id for image in images])


def build_prompt(brand: Brand, images: list[LoadedImage]) -> str:
    values = {
        "brand_name": brand.name or "(not given)",
        "brand_category": brand.category or "(not given)",
        "brand_keywords": ", ".join(brand.keywords) or "(none)",
        "brand_values": brand.values or "(not given)",
        "image_count": str(len(images)),
        "image_ids": ", ".join(image.id for image in images),
    }
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    for key, value in values.items():
        prompt = prompt.replace("{{" + key + "}}", value)
    return prompt


def ask_for_answer(ask: VisionProvider, prompt: str, images: list[LoadedImage]) -> ModelAnswer:
    """Ask the model; if the answer is not valid JSON in our shape, ask once more."""
    try:
        return parse_answer(ask(prompt, images))
    except ValueError as problem:
        first_problem = str(problem)
        log.warning("Model answer was not usable, retrying once: %s", first_problem)

    retry_prompt = (
        f"{prompt}\n\nYour previous answer could not be read ({first_problem}). "
        "Answer again with only the JSON object."
    )
    try:
        return parse_answer(ask(retry_prompt, images))
    except ValueError as problem:
        log.warning("Model answer was not usable after retry: %s", problem)
        raise AiCoreError(
            "invalid_model_output",
            "The AI's answer could not be read, even on a second try. "
            "No traits were made up to fill the gap — please run the extraction again.",
            status=502,
        )


def parse_answer(text: str) -> ModelAnswer:
    """Raises ValueError (which covers JSON and pydantic validation errors) if unusable."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise ValueError("no JSON object in the answer")
    return ModelAnswer.model_validate(json.loads(text[start:end + 1]))


def to_response(answer: ModelAnswer, sent_ids: list[str]) -> ExtractResponse:
    traits = []
    for proposed in answer.traits:
        # Keep only evidence that points at an image we actually sent, without duplicates.
        evidence = [i for i in dict.fromkeys(proposed.evidence_image_ids) if i in sent_ids]
        if not evidence:
            log.warning("Dropped trait %r: no valid evidence images", proposed.name)
            continue
        traits.append(Trait(
            id=f"tr_{len(traits) + 1:02d}",
            name=proposed.name,
            description=proposed.description,
            evidence_image_ids=evidence,
            seen_count=len(evidence),  # counted, not the model's claim
            confidence=proposed.confidence,
            importance=proposed.importance,
            low_confidence=proposed.confidence < LOW_CONFIDENCE_BELOW,
            origin="ai",
        ))
    return ExtractResponse(traits=traits, tone_words=answer.tone_words, colors=answer.colors)
