"""Milestone 1: search metadata only; never download or save source images."""

import hashlib
import os
from urllib.parse import urlsplit

import httpx

from contracts.models import Brand, ImageCandidate, SearchResponse


class SearchError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


def build_query(brand: Brand) -> str:
    # One provider request per search keeps the free allowance predictable.
    return " ".join(part.strip() for part in
                    [brand.name, brand.category, *brand.keywords, "official"]
                    if part.strip())


def valid_url(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        parsed.port  # Reject malformed ports before normalization or display.
        return parsed.scheme in ("http", "https") and bool(parsed.hostname)
    except ValueError:
        return False


def search_images(brand: Brand, dimensions=None, metadata=None) -> SearchResponse:
    if not brand.name.strip():
        raise SearchError(400, "brand_required", "Enter a brand name to search for reference images.")
    if os.getenv("IMAGE_SEARCH_PROVIDER", "").strip().lower() != "serpapi":
        raise SearchError(503, "provider_not_configured", "Set IMAGE_SEARCH_PROVIDER=serpapi in your local .env file.")
    key = os.getenv("IMAGE_SEARCH_API_KEY", "").strip()
    if not key:
        raise SearchError(503, "missing_api_key", "Add your SerpAPI key to IMAGE_SEARCH_API_KEY in your local .env file.")
    try:
        with httpx.Client(timeout=30) as client:
            response = client.get("https://serpapi.com/search.json", params={
                "engine": "google_images", "q": build_query(brand), "api_key": key,
            })
        if response.status_code in (401, 403):
            raise SearchError(503, "invalid_api_key", "Your SerpAPI key was rejected — check the key in your local .env file.")
        if response.status_code == 429:
            raise SearchError(503, "quota_reached", "SerpAPI's search allowance or rate limit was reached — check your dashboard and try later.")
        if response.status_code >= 400:
            raise SearchError(502, "search_failed", "The image search service could not complete this search — try again later.")
        data = response.json()
    except httpx.TimeoutException:
        raise SearchError(504, "search_timeout", "Image search took too long — try again.") from None
    except (httpx.HTTPError, ValueError):
        # Never return the raw exception: request URLs may contain the API key.
        raise SearchError(502, "search_unavailable", "Could not reach the image search service or read its response — try again later.") from None
    if not isinstance(data, dict):
        raise SearchError(502, "invalid_search_response", "The image search service returned an unexpected response — try again later.")
    if data.get("error"):
        error = str(data["error"]).lower()
        if "no results" in error or "hasn't returned any results" in error:
            raise SearchError(404, "no_results", "No reference images found — try adding the product category or different keywords.")
        if "api key" in error:
            raise SearchError(503, "invalid_api_key", "Your SerpAPI key was rejected — check your local .env file.")
        if any(word in error for word in ("quota", "limit", "run out", "credits")):
            raise SearchError(503, "quota_reached", "SerpAPI's search allowance was reached — check your dashboard.")
        raise SearchError(502, "search_failed", "Image search could not complete this request — try again later.")
    results = data.get("images_results", [])
    if not isinstance(results, list):
        raise SearchError(502, "invalid_search_response", "The image search service returned an unexpected response — try again later.")
    candidates = []
    for item in results:
        if not isinstance(item, dict):
            continue
        image, source = item.get("original"), item.get("link")
        if not valid_url(image) or not valid_url(source):
            continue
        if dimensions is not None:
            from .filtering import positive_dimension
            size = (positive_dimension(item.get("original_width")),
                    positive_dimension(item.get("original_height")))
            if any(value is not None for value in size):
                dimensions[image] = size
        thumbnail = item.get("thumbnail")
        if metadata is not None:
            metadata[image] = str(item.get("title") or "")
        candidates.append(ImageCandidate(
            id="img_" + hashlib.sha256(image.encode()).hexdigest()[:16],
            url=image, thumbnail_url=thumbnail if valid_url(thumbnail) else image,
            source_domain=urlsplit(source).hostname.lower(), source_type="search",
            category="other", relevance=None, flagged=False, flag_reason=None, included=True,
        ))
        # Category/relevance and provenance flagging are later milestones.
        # Search position is not a measured relevance score; leave it unknown.
        if len(candidates) == 30:
            break
    if not candidates:
        raise SearchError(404, "no_results", "No usable reference images found — try adding the product category or different keywords.")
    return SearchResponse(candidates=candidates)
