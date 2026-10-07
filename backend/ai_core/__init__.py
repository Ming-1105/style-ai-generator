"""AI core (Person B): trait extraction, embeddings, scoring, directions.

Right now this is only the mock path: it returns the fixtures. Build the real
implementation behind the MOCK_MODE check and keep the mock path working.
"""

import json
import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

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


def not_implemented(what: str) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={"error": {
            "code": "not_implemented",
            "message": f"{what} is not built yet — set MOCK_MODE=1 to use the sample data.",
        }},
    )


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
    return not_implemented("Live design comparison")
