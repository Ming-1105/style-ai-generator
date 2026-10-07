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

from backend.ai_core.errors import AiCoreError
from backend.ai_core.images import LoadedImage

DEFAULT_MODEL = "gemini-3.8-flash"  # 2.5 models are closed to new accounts
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

    request = {
        "url": ENDPOINT.format(model=model),
        "headers": {"x-goog-api-key": os.getenv("VISION_API_KEY", "").strip()},  # never in the URL
        "json": {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
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
                          f"key and that the model \"{model}\" exists (VISION_MODEL).", status=502)
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

    return read_text(response.json())


def read_text(body: dict) -> str:
    block_reason = (body.get("promptFeedback") or {}).get("blockReason")
    if block_reason:
        raise AiCoreError("vision_blocked",
                          f"Gemini declined to look at these images ({block_reason}). Try deselecting some.")
    candidates = body.get("candidates") or []
    parts = (candidates[0].get("content") or {}).get("parts", []) if candidates else []
    return "".join(part.get("text", "") for part in parts)
