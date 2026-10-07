"""The one place that knows which vision model we use.

Everything else in ai_core talks to a "provider": a plain function

    ask(prompt: str, images: list[LoadedImage]) -> str

that sends the prompt and the images to a vision-capable model and returns the model's
text answer. The provider must show each image together with its id (e.g. the text
"Image img_01:" directly before the picture), because the prompt refers to images by id.

To add a provider:
  1. write such a function (in its own file, e.g. provider_<name>.py),
  2. register it in PROVIDERS below under the name used for VISION_PROVIDER in .env.
It reads its key from VISION_API_KEY. Nothing else in ai_core has to change.
"""

import os
from typing import Callable

from backend.ai_core.errors import AiCoreError
from backend.ai_core.images import LoadedImage

VisionProvider = Callable[[str, list[LoadedImage]], str]

# name in VISION_PROVIDER -> function. Empty until we know which provider we have keys for.
PROVIDERS: dict[str, VisionProvider] = {}


def get_provider() -> VisionProvider:
    name = os.getenv("VISION_PROVIDER", "").strip().lower()
    if not name:
        raise AiCoreError(
            "vision_not_configured",
            "No vision model is set up yet — set VISION_PROVIDER and VISION_API_KEY in .env, "
            "or set MOCK_MODE=1 to use the sample data.",
            status=503,
        )
    if name not in PROVIDERS:
        available = ", ".join(sorted(PROVIDERS)) or "none yet"
        raise AiCoreError(
            "vision_not_configured",
            f"There is no connection for the vision provider \"{name}\" (available: {available}).",
            status=503,
        )
    if not os.getenv("VISION_API_KEY", "").strip():
        raise AiCoreError(
            "vision_not_configured",
            f"VISION_PROVIDER is \"{name}\" but VISION_API_KEY is empty in .env.",
            status=503,
        )
    return PROVIDERS[name]
