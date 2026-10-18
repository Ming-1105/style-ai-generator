"""Vision provider for Google Gemini, called over plain HTTPS with httpx (no extra package).

Set in .env:
    VISION_PROVIDER=gemini
    VISION_API_KEY=<key from Google AI Studio>
    VISION_MODEL=<optional, overrides DEFAULT_MODEL>
"""

import base64
import os
import time

import httpx

from backend.ai_core import usage
from backend.ai_core.errors import AiCoreError
from backend.ai_core.images import LoadedImage

DEFAULT_MODEL = "gemini-3.8-flash"  # 2.5 models are closed to new accounts
# VISION_IMAGE_DETAIL: how many tokens (and how much detail) each image gets. Low matched high on our test and costs
# about a quarter of the image tokens, so it is the default; "default" leaves the choice to Google.
IMAGE_DETAIL = {"low": "MEDIA_RESOLUTION_LOW", "medium": "MEDIA_RESOLUTION_MEDIUM", "high": "MEDIA_RESOLUTION_HIGH"}
DEFAULT_IMAGE_DETAIL = "low"
# VISION_THINKING: how much the model thinks before answering. Thinking is billed as output, so on the larger
# models it was most of the cost; "minimal" cut a comparison to about a quarter. "default" leaves it to Google.
THINKING_LEVELS = ("minimal", "low", "medium", "high")
DEFAULT_THINKING = "minimal"
MAX_OUTPUT_TOKENS = 8192  # a ceiling per request (thinking included), so one runaway answer cannot cost much
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TIMEOUT_SECONDS = 120
RETRY_DELAYS = (3, 8)  # seconds to wait before the 2nd and 3rd attempt


def ask(prompt: str, images: list[LoadedImage]) -> str:
    model = os.getenv("VISION_MODEL", "").strip() or DEFAULT_MODEL
    parts = [{"text": prompt}]
    for image in images:
        parts.append({"text": f"Image {image.id}:"})
        parts.append({"inline_data": {
            "mime_type": image.media_type,
            "data": base64.b64encode(image.data).decode("ascii"),
        }})

    usage.check_budget()  # refuse before spending anything if the limit in VISION_BUDGET_USD is reached

    generation_config = {"responseMimeType": "application/json", "temperature": 0.2, "maxOutputTokens": MAX_OUTPUT_TOKENS}
    detail = os.getenv("VISION_IMAGE_DETAIL", "").strip().lower() or DEFAULT_IMAGE_DETAIL
    if detail != "default":
        if detail not in IMAGE_DETAIL:
            raise AiCoreError("vision_not_configured",
                              f"VISION_IMAGE_DETAIL is \"{detail}\" but must be low, medium, high or default.",
                              status=503)
        generation_config["mediaResolution"] = IMAGE_DETAIL[detail]
    thinking = os.getenv("VISION_THINKING", "").strip().lower() or DEFAULT_THINKING
    if thinking != "default":
        if thinking not in THINKING_LEVELS:
            raise AiCoreError("vision_not_configured",
                              f"VISION_THINKING is \"{thinking}\" but must be minimal, low, medium, high or default.",
                              status=503)
        generation_config["thinkingConfig"] = {"thinkingLevel": thinking}

    request = {
        "url": ENDPOINT.format(model=model),
        "headers": {"x-goog-api-key": os.getenv("VISION_API_KEY", "").strip()},  # never in the URL
        "json": {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": generation_config,
        },
        "timeout": TIMEOUT_SECONDS,
    }

    # "High demand" (503) is Google being busy for a moment, so wait and try again.
    for delay in (*RETRY_DELAYS, None):
        try:
            response = httpx.post(**request)
        except httpx.HTTPError:
            raise AiCoreError("vision_unreachable",
                              "Could not reach Gemini — check the internet connection and try again.")
        if response.status_code != 503 or delay is None:
            break
        time.sleep(delay)

    if response.status_code in (400, 401, 403):
        raise AiCoreError("vision_auth",
                          "Gemini refused the request — check that VISION_API_KEY in .env is a valid "
                          f"key, that the model \"{model}\" exists (VISION_MODEL), and that this model accepts "
                          "VISION_THINKING and VISION_IMAGE_DETAIL (set them to default to use the model's own settings).",
                          status=502)
    if response.status_code == 402:
        raise AiCoreError("vision_no_credit",
                          "Google says the prepaid credit for this project is used up or was never added. Buy credit at "
                          "https://aistudio.google.com/billing, or put a key from a project that is still on the free "
                          "tier in VISION_API_KEY.", status=502)
    if response.status_code == 404:
        raise AiCoreError("vision_model_unavailable",
                          f"Gemini does not offer the model \"{model}\" to this account — "
                          "set VISION_MODEL in .env to another model (see aistudio.google.com).",
                          status=502)
    if response.status_code == 429:
        raise AiCoreError("vision_rate_limited",
                          "Gemini says we sent too many requests (free-tier limit) — wait a minute and try again.",
                          status=503)
    if response.status_code >= 400:
        raise AiCoreError("vision_error", f"Gemini returned an error ({response.status_code}) — try again.")

    body = response.json()
    usage.record(model, body.get("usageMetadata"))
    return read_text(body)


def read_text(body: dict) -> str:
    block_reason = (body.get("promptFeedback") or {}).get("blockReason")
    if block_reason:
        raise AiCoreError("vision_blocked",
                          f"Gemini declined to look at these images ({block_reason}). Try deselecting some.")
    candidates = body.get("candidates") or []
    parts = (candidates[0].get("content") or {}).get("parts", []) if candidates else []
    return "".join(part.get("text", "") for part in parts)
