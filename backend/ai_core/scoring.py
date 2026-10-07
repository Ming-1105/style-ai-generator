"""Scoring rules from AGENTS.md, as pure functions (no AI, no I/O).

The model only supplies a score, status and note per trait. Everything derived from
those — overall fit, which gaps matter most, signature-trait departures — is computed
here, so the designer can trace every number back to a trait score and an importance.
"""

from typing import Optional

from contracts.models import CompareResult, Direction, Finding, Trait, TraitScore

SIGNATURE_IMPORTANCE = 80  # importance >= this makes a trait a "signature" trait
SIGNATURE_MIN_SCORE = 40   # a signature trait scoring below this is always a departure


def is_assessed(trait_score: TraitScore) -> bool:
    return trait_score.status in ("ok", "low_confidence") and trait_score.score is not None


def overall_fit(traits: list[Trait], trait_scores: list[TraitScore]) -> Optional[int]:
    """Σ(score × importance) / Σ(importance) over assessed traits.

    Traits that are not_assessable are left out, not counted as 0. Returns None when
    nothing could be assessed (or every assessed trait has importance 0).
    """
    importance = {t.id: t.importance for t in traits}
    assessed = [s for s in trait_scores if is_assessed(s) and s.trait_id in importance]
    total_importance = sum(importance[s.trait_id] for s in assessed)
    if total_importance == 0:
        return None
    weighted = sum(s.score * importance[s.trait_id] for s in assessed)
    return int(weighted / total_importance + 0.5)  # round half up


def rank_gaps(traits: list[Trait], trait_scores: list[TraitScore]) -> list[tuple[str, int]]:
    """(trait_id, gap) pairs, largest gap first, where gap = importance × (100 − score).

    Traits with importance 0, traits that could not be assessed and traits with no gap
    are left out: they never generate a direction.
    """
    importance = {t.id: t.importance for t in traits}
    gaps = []
    for s in trait_scores:
        if not is_assessed(s) or importance.get(s.trait_id, 0) == 0:
            continue
        gap = importance[s.trait_id] * (100 - s.score)
        if gap > 0:
            gaps.append((s.trait_id, gap))
    return sorted(gaps, key=lambda pair: pair[1], reverse=True)


def signature_departures(traits: list[Trait], trait_scores: list[TraitScore]) -> list[Finding]:
    """One departure per signature trait (importance ≥ 80) that scores < 40."""
    by_id = {t.id: t for t in traits}
    findings = []
    for s in trait_scores:
        trait = by_id.get(s.trait_id)
        if trait is None or not is_assessed(s):
            continue
        if trait.importance >= SIGNATURE_IMPORTANCE and s.score < SIGNATURE_MIN_SCORE:
            findings.append(Finding(
                text=f"\"{trait.name}\" is a signature trait (importance {trait.importance}) "
                     f"but scores only {s.score}.",
                trait_ids=[trait.id],
            ))
    return findings


def build_compare_result(
    traits: list[Trait],
    trait_scores: list[TraitScore],
    matches: list[Finding],
    departures: list[Finding],
    directions: list[Direction],
) -> CompareResult:
    """Apply the scoring rules to per-trait judgements and assemble the CompareResult.

    `traits` is the designer's current package, so edits made there (importance changed,
    trait removed, trait added by hand) show up in the result.
    """
    trait_ids = {t.id for t in traits}
    scored_ids = {s.trait_id for s in trait_scores}

    # Only traits that are in the package; a trait nobody judged is not_assessable, never 0.
    scores = [s for s in trait_scores if s.trait_id in trait_ids]
    scores += [
        TraitScore(trait_id=t.id, score=None, status="not_assessable",
                   note="No judgement available for this trait.")
        for t in traits if t.id not in scored_ids
    ]

    def still_applies(item) -> bool:
        # Keep items with no trait link (e.g. a direction outside the current DNA).
        return not item.trait_ids or any(tid in trait_ids for tid in item.trait_ids)

    departures = [d for d in departures if still_applies(d)]
    already_covered = {tid for d in departures for tid in d.trait_ids}
    departures += [f for f in signature_departures(traits, scores)
                   if f.trait_ids[0] not in already_covered]

    # Directions follow the gap ranking; ones whose traits have no gap left (or importance 0)
    # are dropped, and ones with no trait link go last.
    gap = dict(rank_gaps(traits, scores))
    ranked = []
    for d in directions:
        if not d.trait_ids:
            ranked.append((0, d))
        elif any(tid in gap for tid in d.trait_ids):
            ranked.append((max(gap.get(tid, 0) for tid in d.trait_ids), d))
    ranked.sort(key=lambda pair: pair[0], reverse=True)

    return CompareResult(
        overall_fit=overall_fit(traits, scores),
        trait_scores=scores,
        matches=[m for m in matches if still_applies(m)],
        departures=departures,
        directions=[d for _, d in ranked],
    )
