"""AI core (Person B): trait extraction, design comparison, scoring, directions.

With MOCK_MODE=1 the endpoints return the fixtures; otherwise they call the vision model
chosen by VISION_PROVIDER (extract.py, compare.py). Keep the mock path working.
"""

import json
import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from backend.ai_core import usage
from backend.ai_core.compare import compare_design
from backend.ai_core.errors import AiCoreError
from backend.ai_core.extract import extract_dna
from backend.ai_core.provider_gemini import DEFAULT_MODEL as GEMINI_DEFAULT_MODEL
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
        return compare_design(
            body.package, body.design_image, reference_images=body.reference_images,
            additional_design_images=body.additional_design_images,
            design_is_sketch=body.design_is_sketch, design_description=body.design_description,
        )
    except AiCoreError as problem:
        return problem.to_response()


# --- Developer test page (not part of the app's real interface) ---------------------------
# A page for trying the compare step with your own package and design image. It lives here,
# in the AI core's own folder, until the real screen is connected to /api/compare.

DEVTOOLS = Path(__file__).parent / "devtools"


@router.get("/dev/compare", include_in_schema=False)
def dev_compare_page():
    return FileResponse(DEVTOOLS / "compare_test.html")


@router.get("/dev/pipeline", include_in_schema=False)
def dev_pipeline_page():
    return FileResponse(DEVTOOLS / "pipeline_test.html")


@router.get("/dev/usage", include_in_schema=False)
def dev_usage():
    """Tokens and estimated cost of the requests this server has made since it started."""
    return {"summary": usage.session_summary()}


@router.get("/dev/status", include_in_schema=False)
def dev_status():
    """Which mode the server is in, so the page can say whether scores are sample or live."""
    provider = os.getenv("VISION_PROVIDER", "").strip().lower()
    model = os.getenv("VISION_MODEL", "").strip() or (GEMINI_DEFAULT_MODEL if provider == "gemini" else "")
    return {"mock_mode": mock_mode(), "provider": provider, "model": model}


@router.get("/dev/sample-package", include_in_schema=False)
def dev_sample_package():
    return load_fixture("house_style_package.json")
