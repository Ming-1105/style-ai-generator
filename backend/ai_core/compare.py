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
from contracts.models import TRAIT_CATEGORIES, CompareResult, Finding, HouseStylePackage, ImageCandidate, Trait, TraitScore

log = logging.getLogger(__name__)

PROMPT_FILE = Path(__file__).parent / "prompts" / "compare_traits.md"
REFERENCES_FILE = Path(__file__).parent / "prompts" / "compare_references.md"

DESIGN_VIEWS_FILE = Path(__file__).parent / "prompts" / "compare_design_views.md"
DESIGN_SKETCH_FILE = Path(__file__).parent / "prompts" / "compare_design_sketch.md"
DESIGN_DESCRIPTION_FILE = Path(__file__).parent / "prompts" / "compare_design_description.md"
MAX_DESCRIPTION_CHARS = 500
MAX_DESIGN_IMAGES = 4  # the main design plus up to 3 more views
MAX_REFERENCES_PER_TRAIT = 3
MAX_REFERENCES_TOTAL = 12  # distinct images in one request

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
    reference_images: Optional[list[ImageCandidate]] = None,
    additional_design_images: Optional[list[str]] = None,
    design_is_sketch: bool = False,
    design_description: str = "",
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
    sources = [design_image, *(additional_design_images or [])]
    if len(sources) > MAX_DESIGN_IMAGES:
        raise AiCoreError(
            "too_many_design_images",
            f"At most {MAX_DESIGN_IMAGES} design images (the design plus {MAX_DESIGN_IMAGES - 1} more views) can be compared at once.",
            status=422,
        )
    designs = load_designs(sources, load)

    references, refs_by_trait = load_references(package.traits, reference_images or [], load)
    answer = ask_and_parse(
        ask, build_prompt(package, designs, refs_by_trait, design_is_sketch, design_description), [*designs, *references], parse_answer,
        "The AI's answer could not be read, even on a second try. "
        "No scores were made up to fill the gap — please run the comparison again.",
    )
    log.info("View the model saw: %s", answer.view)

    scores = to_trait_scores(package.traits, answer)
    matches, departures = findings_from(package.traits, scores)
    # A second request words concrete directions for the biggest gaps. If it fails, the scores are
    # still returned: the designer loses the suggestions, not the whole comparison.
    try:
        directions = generate_directions(ask, package.brand.name, designs, package.traits, scores)
    except AiCoreError as problem:
        log.warning("No directions this time: %s", problem.message)
        directions = []
    return build_compare_result(package.traits, scores, matches, departures, directions)


def pick_references(traits: list[Trait], candidates: list[ImageCandidate]) -> dict[str, list[ImageCandidate]]:
    """Per trait, up to 3 of its evidence images that were sent along (most relevant first).

    At most 12 distinct images overall, so one request stays affordable. An image cited by several
    traits is counted once. Ids that were not sent are ignored.
    """
    by_id = {c.id: c for c in candidates}
    chosen: dict[str, list[ImageCandidate]] = {}
    distinct: dict[str, ImageCandidate] = {}
    for trait in traits:
        cited = [by_id[i] for i in dict.fromkeys(trait.evidence_image_ids) if i in by_id]
        cited.sort(key=lambda c: c.relevance or 0, reverse=True)
        picks = []
        for image in cited[:MAX_REFERENCES_PER_TRAIT]:
            if image.id not in distinct and len(distinct) >= MAX_REFERENCES_TOTAL:
                continue
            distinct[image.id] = image
            picks.append(image)
        chosen[trait.id] = picks
    return chosen


def load_references(
    traits: list[Trait],
    candidates: list[ImageCandidate],
    load: Callable[[str, str], LoadedImage],
) -> tuple[list[LoadedImage], dict[str, list[str]]]:
    """Download the chosen reference images; return them and, per trait, the ids that did load.

    An image that cannot be downloaded is skipped (the trait is then judged from its description
    and the remaining images). Images live in memory for this request only.
    """
    loaded: dict[str, Optional[LoadedImage]] = {}
    ids_by_trait: dict[str, list[str]] = {}
    for trait_id, images in pick_references(traits, candidates).items():
        ids_by_trait[trait_id] = []
        for image in images:
            if image.id not in loaded:
                try:
                    loaded[image.id] = load(image.id, image.url)
                except ImageLoadError as problem:
                    log.warning("Skipped reference image %s (%s): %s", image.id, image.source_domain, problem)
                    loaded[image.id] = None
            if loaded[image.id] is not None:
                ids_by_trait[trait_id].append(image.id)
    return [image for image in loaded.values() if image is not None], ids_by_trait


def load_designs(sources: list[str], load: Callable[[str, str], LoadedImage]) -> list[LoadedImage]:
    """The main design ("design") and any further views ("design_2", "design_3", ...), in memory only."""
    designs = []
    for number, source in enumerate(sources, start=1):
        label = "design" if number == 1 else f"design_{number}"
        try:
            designs.append(load(label, source))
        except ImageLoadError as problem:
            which = "The design image" if len(sources) == 1 else f"Design image {number} of {len(sources)}"
            raise AiCoreError(
                "design_not_loaded",
                f"{which} could not be used ({problem}) — upload a jpg, png, gif or webp file under 5 MB.",
                status=422,
            )
    return designs


def build_prompt(
    package: HouseStylePackage,
    designs: list[LoadedImage],
    refs_by_trait: Optional[dict[str, list[str]]] = None,
    design_is_sketch: bool = False,
    design_description: str = "",
) -> str:
    # Deliberately name and description only: the model must not see the importance values.
    refs_by_trait = refs_by_trait or {}
    trait_lines = []
    for t in package.traits:
        category = f"[{TRAIT_CATEGORIES[t.category]}] " if t.category in TRAIT_CATEGORIES else ""
        line = f"- {t.id} | {category}{t.name}: {t.description}"
        if refs_by_trait.get(t.id):
            line += f" | reference images: {', '.join(refs_by_trait[t.id])}"
        trait_lines.append(line)
    values = {
        "brand_name": package.brand.name + (f" ({package.brand.product_line})" if package.brand.product_line else "") if package.brand.name else "(not given)",
        "traits": "\n".join(trait_lines),
        "trait_ids": ", ".join(t.id for t in package.traits),
        "design_views_section": views_section(designs),
        "design_context_section": context_section(design_is_sketch, design_description),
        "reference_section": REFERENCES_FILE.read_text(encoding="utf-8") if any(refs_by_trait.values()) else "",
    }
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    for key, value in values.items():
        prompt = prompt.replace("{{" + key + "}}", value)
    return prompt


def context_section(is_sketch: bool, description: str) -> str:
    """What the designer told us about the design: a sketch (no colour or material judged) and/or a short description."""
    text = DESIGN_SKETCH_FILE.read_text(encoding="utf-8") if is_sketch else ""
    # One line of limited length; the text is the designer's own words and is shown to the model as information only.
    description = " ".join(description.split())[:MAX_DESCRIPTION_CHARS].replace('"', "'")
    if description:
        text += DESIGN_DESCRIPTION_FILE.read_text(encoding="utf-8").replace("{{description}}", description)
    return text


def views_section(designs: list[LoadedImage]) -> str:
    """Extra prompt text, only when the design comes as more than one view."""
    if len(designs) < 2:
        return ""
    text = DESIGN_VIEWS_FILE.read_text(encoding="utf-8")
    labels = ", ".join(f'"Image {d.id}"' for d in designs)
    return text.replace("{{design_count}}", str(len(designs))).replace("{{design_labels}}", labels)


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
