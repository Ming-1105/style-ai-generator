"""Tests for token and cost tracking and the spending limit. Nothing here touches the real ledger."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from backend.ai_core import provider_gemini, usage
from backend.ai_core.errors import AiCoreError
from backend.ai_core.images import LoadedImage

IMAGES = [LoadedImage("img_01", "image/png", b"x")]
USAGE = {"promptTokenCount": 2139, "candidatesTokenCount": 331, "thoughtsTokenCount": 1229}


def reply(usage_metadata=None, text="{}"):
    body = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    if usage_metadata is not None:
        body["usageMetadata"] = usage_metadata
    return httpx.Response(200, json=body, request=httpx.Request("POST", "https://x"))


class LedgerCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.ledger = Path(folder.name) / "ledger.jsonl"
        env = patch.dict(os.environ, {"VISION_USAGE_LEDGER": str(self.ledger), "VISION_BUDGET_USD": "",
                                      "VISION_API_KEY": "k", "VISION_MODEL": "gemini-3.5-flash"})
        env.start()
        self.addCleanup(env.stop)
        session = patch.object(usage, "_session", [])
        session.start()
        self.addCleanup(session.stop)


class CostTests(unittest.TestCase):
    def test_cost_follows_the_price_table(self):
        cost, known = usage.estimate_cost("gemini-3.5-flash-lite", 2139, 331)
        self.assertTrue(known)
        self.assertAlmostEqual(cost, 2139 * 0.30 / 1e6 + 331 * 2.50 / 1e6, places=9)

    def test_an_unknown_model_is_priced_at_the_highest_known_rate(self):
        cost, known = usage.estimate_cost("some-new-model", 1_000_000, 0)
        self.assertFalse(known)
        self.assertEqual(cost, 2.00)


class RecordTests(LedgerCase):
    def test_thinking_tokens_are_billed_as_output(self):
        entry = usage.record("gemini-3.5-flash", USAGE)
        self.assertEqual((entry["input"], entry["output"], entry["thinking"]), (2139, 331 + 1229, 1229))
        self.assertAlmostEqual(entry["cost_usd"], (2139 * 1.50 + 1560 * 9.00) / 1e6, places=5)

    def test_entries_are_appended_to_the_ledger_and_totalled(self):
        usage.record("gemini-3.5-flash", USAGE)
        usage.record("gemini-3.5-flash", USAGE)
        self.assertEqual(len(self.ledger.read_text(encoding="utf-8").splitlines()), 2)
        self.assertAlmostEqual(usage.ledger_total_usd(), 2 * (2139 * 1.50 + 1560 * 9.00) / 1e6, places=5)

    def test_no_usage_data_records_nothing(self):
        self.assertIsNone(usage.record("gemini-3.5-flash", None))
        self.assertFalse(self.ledger.exists())

    def test_a_damaged_ledger_line_is_ignored(self):
        self.ledger.write_text('not json\n{"cost_usd": 0.25}\n', encoding="utf-8")
        self.assertEqual(usage.ledger_total_usd(), 0.25)

    def test_summary_names_requests_tokens_and_cost(self):
        usage.record("gemini-3.5-flash", USAGE)
        text = usage.session_summary()
        self.assertIn("1 request,", text)
        self.assertIn("2,139 tokens in", text)
        self.assertIn("1,229 of them thinking", text)
        self.assertIn("about $0.0", text)


class BudgetTests(LedgerCase):
    def test_no_limit_means_no_check(self):
        self.ledger.write_text('{"cost_usd": 999}\n', encoding="utf-8")
        usage.check_budget()  # does not raise

    def test_under_the_limit_is_fine(self):
        self.ledger.write_text('{"cost_usd": 1.0}\n', encoding="utf-8")
        with patch.dict(os.environ, {"VISION_BUDGET_USD": "5"}):
            usage.check_budget()

    def test_at_the_limit_requests_are_refused_with_a_clear_message(self):
        self.ledger.write_text('{"cost_usd": 5.0}\n', encoding="utf-8")
        with patch.dict(os.environ, {"VISION_BUDGET_USD": "5"}), self.assertRaises(AiCoreError) as raised:
            usage.check_budget()
        self.assertEqual(raised.exception.code, "budget_reached")
        self.assertIn("$5.00", raised.exception.message)

    def test_a_limit_that_is_not_a_number_is_reported(self):
        with patch.dict(os.environ, {"VISION_BUDGET_USD": "five"}), self.assertRaises(AiCoreError) as raised:
            usage.check_budget()
        self.assertEqual(raised.exception.code, "vision_not_configured")


class ProviderIntegrationTests(LedgerCase):
    def test_a_successful_request_is_recorded(self):
        with patch("httpx.post", return_value=reply(USAGE)):
            provider_gemini.ask("p", IMAGES)
        self.assertEqual(len(usage._session), 1)
        self.assertEqual(usage._session[0]["model"], "gemini-3.5-flash")

    def test_a_response_without_usage_data_still_works(self):
        with patch("httpx.post", return_value=reply(None)):
            self.assertEqual(provider_gemini.ask("p", IMAGES), "{}")
        self.assertEqual(usage._session, [])

    def test_when_the_limit_is_reached_no_request_is_sent(self):
        self.ledger.write_text('{"cost_usd": 5.0}\n', encoding="utf-8")
        with patch.dict(os.environ, {"VISION_BUDGET_USD": "5"}), patch("httpx.post") as post, \
                self.assertRaises(AiCoreError) as raised:
            provider_gemini.ask("p", IMAGES)
        self.assertEqual(raised.exception.code, "budget_reached")
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
