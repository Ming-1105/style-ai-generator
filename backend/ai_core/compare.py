"""Design comparison: uploaded design + House Style Package -> CompareResult.

The model judges each trait (score, status, note). Everything else is decided in code:
which statuses are allowed, what happens to a trait the model skipped, which judgements
become matches or departures, and how the overall fit follows from the scores and the
designer's importance values (scoring.py). The model is never shown the importance values.
"""

import logging
from pathlib import Path
from typing import Callable, Literal, Optional

from pydantic import BaseModel, Field

from backend.ai_core.directions import generate_directions
from backend.ai_core.errors import AiCoreError
from backend.ai_core.images import ImageLoadError, LoadedImage, load_image
from backend.ai_core.model_call import ask_and_parse, read_json_object
from backend.ai_core.providers import VisionProvider, get_provider
from backend.ai_core.scoring import build_compare_result
from contracts.models import CompareResult, Finding, HouseStylePackage, Trait, TraitScore

log = logging.getLogger(__name__)

PROMPT_FILE = Path(__file__).parent / "prompts" / "compare_traits.md"

MATCH_MIN_SCORE = 70        # at or above: listed under "matches the brand"
DEPARTURE_BELOW_SCORE = 50  # below: listed under "departs from the brand"; 50-69 only in the scores


class ModelJudgement(BaseModel):
    """One trait as the model is asked to judge it (see prompts/compare_traits.md)."""

    trait_id: str
    score: Optional[float] = Field(default=None, ge=0, le=100)
    status: Literal["ok", "not_assessable"]
    note: str = ""


class ModelAnswer(BaseModel):
    view: str = ""
    traits: list[ModelJudgement]


def compare_design(
    package: HouseStylePackage,
    design_image: str,
    ask: Optional[VisionProvider] = None,
    load: Optional[Callable[[str, str], LoadedImage]] = None,
) -> CompareResult:
    """`ask` and `load` can be replaced in tests, so no API key or network is needed."""
    ask = ask or get_provider()  # fail early if no model is set up
    load = load or load_image

    if not package.traits:
        raise AiCoreError(
            "no_traits",
            "The house style package has no traits to compare against — keep or add at least one trait.",
            status=422,
        )
    try:
        design = load("design", design_image)
    except ImageLoadError as problem:
        raise AiCoreError(
            "design_not_loaded",
            f"The design image could not be used ({problem}) — upload a jpg, png, gif or webp file under 5 MB.",
            status=422,
        )

    answer = ask_and_parse(
        ask, build_prompt(package, design), [design], parse_answer,
        "The AI's answer could not be read, even on a second try. "
        "No scores were made up to fill the gap — please run the comparison again.",
    )
    log.info("View the model saw: %s", answer.view)

    scores = to_trait_scores(package.traits, answer)
    matches, departures = findings_from(package.traits, scores)
    # A second request words concrete directions for the biggest gaps. If it fails, the scores are
    # still returned: the designer loses the suggestions, not the whole comparison.
    try:
        directions = generate_directions(ask, package.brand.name, design, package.traits, scores)
    except AiCoreError as problem:
        log.warning("No directions this time: %s", problem.message)
        directions = []
    return build_compare_result(package.traits, scores, matches, departures, directions)


def build_prompt(package: HouseStylePackage, design: LoadedImage) -> str:
    # Deliberately name and description only: the model must not see the importance values.
    trait_lines = [f"- {t.id} | {t.name}: {t.description}" for t in package.traits]
    values = {
        "brand_name": package.brand.name or "(not given)",
        "traits": "\n".join(trait_lines),
        "trait_ids": ", ".join(t.id for t in package.traits),
    }
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    for key, value in values.items():
        prompt = prompt.replace("{{" + key + "}}", value)
    return prompt


def parse_answer(text: str) -> ModelAnswer:
    """Raises ValueError (which covers JSON and pydantic validation errors) if unusable."""
    return ModelAnswer.model_validate(read_json_object(text))


def to_trait_scores(traits: list[Trait], answer: ModelAnswer) -> list[TraitScore]:
    """One TraitScore per trait in the package, in package order, whatever the model returned."""
    judged: dict[str, ModelJudgement] = {}
    for judgement in answer.traits:
        judged.setdefault(judgement.trait_id, judgement)  # first one wins; unknown ids never match

    scores = []
    for trait in traits:
        judgement = judged.get(trait.id)
        if judgement is None:
            scores.append(not_assessable(trait, "The AI gave no judgement for this trait."))
        elif judgement.status == "not_assessable":
            scores.append(not_assessable(trait, judgement.note.strip() or "Not visible in this design."))
        elif judgement.score is None:
            scores.append(not_assessable(trait, "The AI gave no score for this trait."))
        else:
            scores.append(TraitScore(
                trait_id=trait.id,
                score=round(judgement.score),
                # A trait the AI itself was unsure about at extraction time stays flagged.
                status="low_confidence" if trait.low_confidence else "ok",
                note=judgement.note.strip(),
            ))
    return scores


def not_assessable(trait: Trait, note: str) -> TraitScore:
    return TraitScore(trait_id=trait.id, score=None, status="not_assessable", note=note)


def findings_from(traits: list[Trait], scores: list[TraitScore]) -> tuple[list[Finding], list[Finding]]:
    """Matches and departures, taken from the per-trait notes. No extra model call."""
    matches, departures = [], []
    for trait, score in zip(traits, scores):
        finding = Finding(text=score.note or trait.name, trait_ids=[trait.id])
        if score.status == "not_assessable":
            departures.append(finding)  # so the designer sees what could not be judged
        elif score.score >= MATCH_MIN_SCORE:
            matches.append(finding)
        elif score.score < DEPARTURE_BELOW_SCORE:
            departures.append(finding)
    return matches, departures
