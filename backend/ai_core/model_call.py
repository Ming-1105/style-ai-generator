"""Ask a vision model for a JSON answer and read it, with one retry.

Shared by trait extraction and design comparison, so both fail the same honest way:
an answer we cannot read is retried once and then reported, never replaced by guesses.
"""

import json
import logging
from typing import Callable, TypeVar

from backend.ai_core.errors import AiCoreError
from backend.ai_core.images import LoadedImage
from backend.ai_core.providers import VisionProvider

log = logging.getLogger(__name__)
T = TypeVar("T")


def read_json_object(text: str) -> dict:
    """The JSON object in the model's text (it may be wrapped in a code fence or a sentence).

    Raises ValueError (json.JSONDecodeError is one) if there is none.
    """
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise ValueError("no JSON object in the answer")
    return json.loads(text[start:end + 1])


def ask_and_parse(
    ask: VisionProvider,
    prompt: str,
    images: list[LoadedImage],
    parse: Callable[[str], T],
    failure_message: str,
) -> T:
    """Ask the model; if `parse` raises ValueError (pydantic's errors are one), ask once more."""
    try:
        return parse(ask(prompt, images))
    except ValueError as problem:
        first_problem = str(problem)
        log.warning("Model answer was not usable, retrying once: %s", first_problem)

    retry_prompt = (
        f"{prompt}\n\nYour previous answer could not be read ({first_problem}). "
        "Answer again with only the JSON object."
    )
    try:
        return parse(ask(retry_prompt, images))
    except ValueError as problem:
        log.warning("Model answer was not usable after retry: %s", problem)
        raise AiCoreError("invalid_model_output", failure_message, status=502)
