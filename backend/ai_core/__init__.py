"""AI core (Person B): trait extraction, design comparison, scoring, directions.

With MOCK_MODE=1 the endpoints return the fixtures; otherwise they call the vision model
chosen by VISION_PROVIDER (extract.py, compare.py). Keep the mock path working.
"""

import json
import os
from pathlib import Path

from fastapi import APIRouter

from backend.ai_core.compare import compare_design
from backend.ai_core.errors import AiCoreError
from backend.ai_core.extract import extract_dna
from backend.ai_core.scoring import build_compare_result
from contracts.models import CompareRequest, CompareResult, ExtractRequest, ExtractResponse

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

router = APIRouter(prefix="/api", tags=["ai_core"])


def mock_mode() -> bool:
    return os.getenv("MOCK_MODE", "1") == "1"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@router.post("/dna/extract", response_model=ExtractResponse)
def extract(body: ExtractRequest):
    if mock_mode():
        return load_fixture("dna_extract.json")
    try:
        return extract_dna(body.brand, body.images)
    except AiCoreError as problem:
        return problem.to_response()


@router.post("/compare", response_model=CompareResult)
def compare(body: CompareRequest):
    if mock_mode():
        # The per-trait judgements are sample data; everything derived from them is
        # computed from the package that was sent, so editing an importance changes the result.
        sample = CompareResult(**load_fixture("compare.json"))
        return build_compare_result(
            body.package.traits,
            sample.trait_scores,
            sample.matches,
            sample.departures,
            sample.directions,
        )
    try:
        return compare_design(body.package, body.design_image)
    except AiCoreError as problem:
        return problem.to_response()
