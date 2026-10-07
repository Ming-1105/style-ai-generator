"""Sourcing (Person A): image search, scraping known URLs, dedupe, flagging.

Mock mode returns the fixture; live mode searches SerpAPI using local configuration.
"""

import json
import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from contracts.models import SearchRequest, SearchResponse
from .serpapi import SearchError, search_images

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
    try:
        return search_images(body.brand)
    except SearchError as exc:
        return JSONResponse(status_code=exc.status, content={"error": {
            "code": exc.code, "message": exc.message,
        }})

