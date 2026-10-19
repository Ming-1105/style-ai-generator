"""Pydantic models for the data contract in AGENTS.md.

Shared file: do not change it on your own. Propose changes in docs/contract-changes.md.

Conventions: IDs are strings, scores are 0-100 integers, confidence is a 0-1 float,
and None means "could not be determined" (never replace it with a made-up number).
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------- Brand ----------

class Brand(BaseModel):
    name: str = ""
    category: str = ""
    website: str = ""
    keywords: list[str] = []
    values: str = ""


# ---------- Sourcing ----------

class ImageCandidate(BaseModel):
    id: str
    url: str
    thumbnail_url: str
    source_domain: str
    source_type: Literal["search", "scrape", "presskit", "upload"]
    category: Literal["product", "logo", "packaging", "web", "other"]
    relevance: Optional[float] = Field(default=None, ge=0, le=1)
    flagged: bool = False
    flag_reason: Optional[str] = None  # e.g. "Fan render — not official"
    included: bool = True  # designer's choice; flagged images default to False


# ---------- Style DNA ----------

class Trait(BaseModel):
    id: str
    name: str
    description: str
    evidence_image_ids: list[str] = []
    seen_count: int = Field(default=0, ge=0)  # number of included images showing it
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    importance: int = Field(ge=0, le=100)  # set by the designer (AI may suggest a default)
    low_confidence: bool = False  # True when confidence < 0.6
    origin: Literal["ai", "manual"]


class Color(BaseModel):
    name: str
    hex: str


class DoDont(BaseModel):
    do: str
    dont: str


class HouseStylePackage(BaseModel):
    version: int = 1
    created_at: str  # ISO 8601, e.g. "2026-10-05T12:00:00Z"
    brand: Brand
    traits: list[Trait]
    tone_words: list[str] = []
    colors: list[Color] = []
    do_dont: list[DoDont] = []
    source_image_ids: list[str] = []


# ---------- Compare ----------

class TraitScore(BaseModel):
    trait_id: str
    score: Optional[int] = Field(default=None, ge=0, le=100)  # None when not_assessable
    status: Literal["ok", "low_confidence", "not_assessable"]
    note: str = ""


class Finding(BaseModel):
    """One entry in CompareResult.matches or CompareResult.departures."""

    text: str
    trait_ids: list[str] = []


class Direction(BaseModel):
    id: str
    title: str
    rationale: str
    trait_ids: list[str] = []
    image_url: Optional[str] = None  # image optional


class CompareResult(BaseModel):
    overall_fit: Optional[int] = Field(default=None, ge=0, le=100)  # None if no trait could be assessed
    trait_scores: list[TraitScore]
    matches: list[Finding] = []
    departures: list[Finding] = []
    directions: list[Direction] = []
    coverage: Optional[int] = Field(default=None, ge=0, le=100)  # % of the total importance that could be judged


# ---------- API request / response bodies ----------

class SearchRequest(BaseModel):
    brand: Brand


class SearchResponse(BaseModel):
    candidates: list[ImageCandidate]


class ExtractRequest(BaseModel):
    brand: Brand
    images: list[ImageCandidate]


class SkippedImage(BaseModel):
    """An image that was selected but not analysed, and why. Shown to the designer."""

    id: str
    reason: str


class ExtractResponse(BaseModel):
    traits: list[Trait]
    tone_words: list[str] = []
    colors: list[Color] = []
    do_dont: list[DoDont] = []  # design rules drawn from the traits (optional)
    skipped_images: list[SkippedImage] = []  # selected images that could not be analysed (optional)


class CompareRequest(BaseModel):
    package: HouseStylePackage
    design_image: str  # data URL or https URL
    additional_design_images: list[str] = []  # more views of the same design (optional, at most 3)
    reference_images: list[ImageCandidate] = []  # the images cited as evidence by the traits (optional)
    design_is_sketch: bool = False  # the designer says it is a sketch or black and white: colour and material are not judged (optional)
    design_description: str = ""  # a short text from the designer about the design (optional, at most 500 characters are used)


# ---------- Errors ----------

class ErrorDetail(BaseModel):
    code: str
    message: str  # written for the designer


class ErrorResponse(BaseModel):
    error: ErrorDetail
