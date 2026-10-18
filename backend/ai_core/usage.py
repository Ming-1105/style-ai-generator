"""Token use and estimated cost of the vision requests, with an optional spending limit.

Every successful request is appended to a ledger file (one JSON object per line) with the tokens
Google reported and an estimated cost. If VISION_BUDGET_USD is set, requests are refused once the
ledger total reaches it. This is a safety net for a prepaid budget, not accounting: the estimate
uses the price table below (Google's published prices, checked 2026-10-13), so compare it with the
real usage in Google AI Studio now and then. The limit can be overshot by at most one request.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.ai_core.errors import AiCoreError

# model -> (USD per 1M input tokens, USD per 1M output tokens). Output includes the hidden thinking tokens.
PRICES = {
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.5-flash": (1.50, 9.00),
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-3.1-pro-preview": (2.00, 12.00),  # prompts up to 200k tokens
}
FALLBACK_PRICE = (2.00, 12.00)  # an unknown model is priced at the highest known rate, so the limit errs on the safe side

DEFAULT_LEDGER = Path(__file__).resolve().parents[2] / "usage_ledger.jsonl"

_session: list[dict] = []  # requests made since this process started


def ledger_path() -> Path:
    return Path(os.getenv("VISION_USAGE_LEDGER", "").strip() or DEFAULT_LEDGER)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> tuple[float, bool]:
    """(estimated USD, whether the model's price was known)."""
    price = PRICES.get(model)
    known = price is not None
    per_input, per_output = price or FALLBACK_PRICE
    return (input_tokens * per_input + output_tokens * per_output) / 1_000_000, known


def record(model: str, usage_metadata: Optional[dict]) -> Optional[dict]:
    """Add one request to the session totals and the ledger. Does nothing without usage data."""
    if not usage_metadata:
        return None
    input_tokens = int(usage_metadata.get("promptTokenCount") or 0)
    thinking = int(usage_metadata.get("thoughtsTokenCount") or 0)
    output_tokens = int(usage_metadata.get("candidatesTokenCount") or 0) + thinking  # thinking is billed as output
    cost, known = estimate_cost(model, input_tokens, output_tokens)
    entry = {
        "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": model, "input": input_tokens, "output": output_tokens, "thinking": thinking,
        "cost_usd": round(cost, 6), "price_known": known,
    }
    _session.append(entry)
    try:
        with ledger_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # a ledger that cannot be written must never break a comparison
    return entry


def ledger_total_usd() -> float:
    path = ledger_path()
    if not path.exists():
        return 0.0
    total = 0.0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            total += float(json.loads(line).get("cost_usd", 0))
        except (ValueError, AttributeError):
            continue  # ignore a damaged line
    return total


def budget_usd() -> Optional[float]:
    raw = os.getenv("VISION_BUDGET_USD", "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        raise AiCoreError("vision_not_configured",
                          f"VISION_BUDGET_USD is \"{raw}\" but must be a number of dollars, e.g. 5.", status=503)


def check_budget() -> None:
    """Refuse the request when the recorded spend has reached VISION_BUDGET_USD."""
    limit = budget_usd()
    if limit is None:
        return
    spent = ledger_total_usd()
    if spent >= limit:
        raise AiCoreError(
            "budget_reached",
            f"The spending limit of ${limit:.2f} (VISION_BUDGET_USD) is reached: about ${spent:.2f} has been used "
            f"according to {ledger_path().name}. Raise the limit in .env, or delete that file to start counting again.",
            status=429,
        )


def session_summary() -> str:
    """One readable line about this run, plus the ledger total against the limit."""
    if not _session:
        return "No token use was recorded in this run."
    requests = len(_session)
    tokens_in = sum(e["input"] for e in _session)
    tokens_out = sum(e["output"] for e in _session)
    thinking = sum(e["thinking"] for e in _session)
    cost = sum(e["cost_usd"] for e in _session)
    text = (f"This run: {requests} request{'s' if requests != 1 else ''}, {tokens_in:,} tokens in, {tokens_out:,} out "
            f"({thinking:,} of them thinking), about ${cost:.4f}.")
    limit = budget_usd()
    total = ledger_total_usd()
    text += f" Recorded so far: ${total:.2f}" + (f" of your ${limit:.2f} limit." if limit is not None else ".")
    if any(not e["price_known"] for e in _session):
        text += " (A model without a known price was counted at the highest rate.)"
    return text
