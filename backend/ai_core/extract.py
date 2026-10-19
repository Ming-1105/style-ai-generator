"""Trait extraction: included images + brand info -> Style DNA traits.

The model proposes traits and says which images show each one. Everything that can be
checked or counted is done here in code rather than taken on trust: evidence ids must be
images we actually sent, seen_count is counted from them, and low_confidence follows
from the confidence value.
"""

import logging
from pathlib import Path
from typing import Callable, Optional

from pydantic import BaseModel, Field

from backend.ai_core.errors import AiCoreError
from backend.ai_core.images import ImageLoadError, LoadedImage, load_image
from backend.ai_core.model_call import ask_and_parse, read_json_object
from backend.ai_core.providers import VisionProvider, get_provider
from contracts.models import Brand, Color, DoDont, ExtractResponse, ImageCandidate, SkippedImage, Trait

log = logging.getLogger(__name__)

PROMPT_FILE = Path(__file__).parent / "prompts" / "extract_traits.md"

MAX_IMAGES = 20             # most relevant first; keeps one request affordable
MIN_IMAGES = 2              # "recurring" needs at least two images
LOW_CONFIDENCE_BELOW = 0.6  # AGENTS.md
MAX_RULES = 6               # do/don't pairs returned


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
    do_dont: list[DoDont] = []


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
    # Everything that is selected but not analysed is reported to the designer, with the reason.
    skipped = [SkippedImage(id=c.id, reason=f"not analysed: only the {MAX_IMAGES} most relevant images are used")
               for c in included[MAX_IMAGES:]]
    included = included[:MAX_IMAGES]

    images = []
    for candidate in included:
        try:
            images.append(load(candidate.id, candidate.url))
        except ImageLoadError as problem:
            log.warning("Skipped %s (%s): %s", candidate.id, candidate.source_domain, problem)
            skipped.append(SkippedImage(id=candidate.id, reason=str(problem)))

    if len(images) < MIN_IMAGES:
        raise AiCoreError(
            "too_few_images",
            f"Only {len(images)} of the {len(included)} selected images could be loaded — "
            f"the AI needs at least {MIN_IMAGES} to find recurring traits. "
            "Try including more images or adding some by upload.",
            status=422,
        )

    answer = ask_for_answer(ask, build_prompt(brand, images), images)
    return to_response(answer, sent_ids=[image.id for image in images], skipped=skipped)


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
    return ask_and_parse(
        ask, prompt, images, parse_answer,
        "The AI's answer could not be read, even on a second try. "
        "No traits were made up to fill the gap — please run the extraction again.",
    )


def parse_answer(text: str) -> ModelAnswer:
    """Raises ValueError (which covers JSON and pydantic validation errors) if unusable."""
    return ModelAnswer.model_validate(read_json_object(text))


def clean_rules(rules: list[DoDont]) -> list[DoDont]:
    """Keep only complete do/don't pairs (both sides written), at most MAX_RULES."""
    kept = []
    for rule in rules:
        do, dont = rule.do.strip(), rule.dont.strip()
        if do and dont:
            kept.append(DoDont(do=do, dont=dont))
    return kept[:MAX_RULES]


def to_response(answer: ModelAnswer, sent_ids: list[str], skipped: Optional[list[SkippedImage]] = None) -> ExtractResponse:
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
    return ExtractResponse(traits=traits, tone_words=answer.tone_words, colors=answer.colors,
                           do_dont=clean_rules(answer.do_dont), skipped_images=skipped or [])
