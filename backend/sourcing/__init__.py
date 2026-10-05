"""Sourcing (Person A): image search, scraping known URLs, dedupe, flagging.

Right now this is only the mock path: it returns the fixture. Build the real
implementation behind the MOCK_MODE check and keep the mock path working.
"""

import json
import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from contracts.models import SearchRequest, SearchResponse

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

router = APIRouter(prefix="/api/sources", tags=["sourcing"])


def mock_mode() -> bool:
    return os.getenv("MOCK_MODE", "1") == "1"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@router.post("/search", response_model=SearchResponse)
def search(body: SearchRequest):
    if mock_mode():
        return load_fixture("sources_search.json")
    return JSONResponse(
        status_code=501,
        content={"error": {
            "code": "not_implemented",
            "message": "Live image search is not built yet — set MOCK_MODE=1 to use the sample data.",
        }},
    )
