"""Suggested design directions, taken from the biggest gaps between the design and the brand.

Code decides which traits matter (largest gap = importance x (100 - score), importance 0 never
counts, AGENTS.md), so the model never sees the importance values. The model only words
concrete suggestions for those traits. Everything it returns is checked here: trait ids must be
ones we sent, a direction without a valid trait is dropped, at most 3 are kept, and they are
ordered by gap. No image is generated: image_url stays null.
"""

import logging
from pathlib import Path

from pydantic import BaseModel, Field

from backend.ai_core.images import LoadedImage
from backend.ai_core.model_call import ask_and_parse, read_json_object
from backend.ai_core.providers import VisionProvider
from backend.ai_core.scoring import rank_gaps
from contracts.models import Direction, Trait, TraitScore

log = logging.getLogger(__name__)

PROMPT_FILE = Path(__file__).parent / "prompts" / "directions.md"
MAX_DIRECTIONS = 3
MAX_GAP_TRAITS = 3  # how many of the biggest gaps are shown to the model


class ModelDirection(BaseModel):
    title: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    trait_ids: list[str]


class ModelDirections(BaseModel):
    directions: list[ModelDirection]


def pick_gap_traits(traits: list[Trait], scores: list[TraitScore]) -> list[tuple[Trait, TraitScore, int]]:
    """The traits with the biggest gaps, biggest first, as (trait, score, gap)."""
    by_id = {t.id: t for t in traits}
    score_by_id = {s.trait_id: s for s in scores}
    return [(by_id[tid], score_by_id[tid], gap) for tid, gap in rank_gaps(traits, scores)[:MAX_GAP_TRAITS]]


def build_prompt(brand_name: str, gap_traits: list[tuple[Trait, TraitScore, int]]) -> str:
    # Name, description, score and the observation only. Never the importance or the gap.
    lines = [
        f"- {trait.id} | {trait.name}: {trait.description} | scored {score.score} | observed: {score.note or 'no note'}"
        for trait, score, _ in gap_traits
    ]
    values = {
        "brand_name": brand_name or "(not given)",
        "gaps": "\n".join(lines),
        "trait_ids": ", ".join(trait.id for trait, _, _ in gap_traits),
    }
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    for key, value in values.items():
        prompt = prompt.replace("{{" + key + "}}", value)
    return prompt


def parse_answer(text: str) -> ModelDirections:
    """Raises ValueError (which covers JSON and pydantic validation errors) if unusable."""
    return ModelDirections.model_validate(read_json_object(text))


def to_directions(answer: ModelDirections, gap_by_trait: dict[str, int]) -> list[Direction]:
    """Keep only valid directions, ordered by the size of the gap they address."""
    kept = []
    for proposed in answer.directions:
        trait_ids = [i for i in dict.fromkeys(proposed.trait_ids) if i in gap_by_trait]
        if not trait_ids:
            log.warning("Dropped direction %r: it names no trait we sent", proposed.title)
            continue
        kept.append((max(gap_by_trait[i] for i in trait_ids), proposed, trait_ids))
    kept.sort(key=lambda item: item[0], reverse=True)  # stable: the model's order breaks ties
    return [
        Direction(id=f"dir_{chr(ord('a') + number)}", title=proposed.title.strip(),
                  rationale=proposed.rationale.strip(), trait_ids=trait_ids, image_url=None)
        for number, (_, proposed, trait_ids) in enumerate(kept[:MAX_DIRECTIONS])
    ]


def generate_directions(
    ask: VisionProvider,
    brand_name: str,
    design: LoadedImage,
    traits: list[Trait],
    scores: list[TraitScore],
) -> list[Direction]:
    """Up to 3 directions for the biggest gaps; an empty list when there is no gap to work on.

    Raises AiCoreError when the model's answer stays unreadable after one retry.
    """
    gap_traits = pick_gap_traits(traits, scores)
    if not gap_traits:
        return []  # nothing assessed, or everything fits, or the weighty traits have importance 0
    answer = ask_and_parse(
        ask, build_prompt(brand_name, gap_traits), [design], parse_answer,
        "The AI's suggestions could not be read, even on a second try. No directions were made up.",
    )
    return to_directions(answer, {trait.id: gap for trait, _, gap in gap_traits})
