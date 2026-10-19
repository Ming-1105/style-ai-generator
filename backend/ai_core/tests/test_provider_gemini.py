"""Tests for the Gemini connection. The web request is faked: no key, no network."""

import base64
import os
import unittest
from unittest.mock import patch

import httpx

from backend.ai_core import provider_gemini
from backend.ai_core.errors import AiCoreError
from backend.ai_core.images import LoadedImage

IMAGES = [LoadedImage("img_01", "image/jpeg", b"aaa"), LoadedImage("img_02", "image/png", b"bbb")]
ENV = {"VISION_API_KEY": "secret-key", "VISION_MODEL": ""}


def reply(status=200, json=None):
    return httpx.Response(status, json=json or {}, request=httpx.Request("POST", "https://x"))


def answer(text):
    return reply(json={"candidates": [{"content": {"parts": [{"text": text}]}}]})


class RequestTests(unittest.TestCase):
    def ask(self, response):
        with patch.dict(os.environ, ENV), patch("httpx.post", return_value=response) as post:
            result = provider_gemini.ask("PROMPT", IMAGES)
        return result, post

    def test_returns_the_text_of_the_answer(self):
        result, _ = self.ask(answer('{"traits": []}'))
        self.assertEqual(result, '{"traits": []}')

    def test_each_image_is_labelled_with_its_id_and_sent_as_data(self):
        _, post = self.ask(answer("{}"))
        parts = post.call_args.kwargs["json"]["contents"][0]["parts"]
        self.assertEqual(parts[0], {"text": "PROMPT"})
        self.assertEqual(parts[1], {"text": "Image img_01:"})
        self.assertEqual(parts[2]["inline_data"],
                         {"mime_type": "image/jpeg", "data": base64.b64encode(b"aaa").decode()})
        self.assertEqual(parts[3], {"text": "Image img_02:"})

    def test_key_goes_in_a_header_never_in_the_url(self):
        _, post = self.ask(answer("{}"))
        self.assertEqual(post.call_args.kwargs["headers"]["x-goog-api-key"], "secret-key")
        self.assertNotIn("secret-key", post.call_args.kwargs["url"])

    def test_model_can_be_overridden(self):
        with patch.dict(os.environ, {**ENV, "VISION_MODEL": "gemini-test"}), \
                patch("httpx.post", return_value=answer("{}")) as post:
            provider_gemini.ask("p", IMAGES)
        self.assertIn("gemini-test:generateContent", post.call_args.kwargs["url"])


class ImageDetailTests(unittest.TestCase):
    def config_sent(self, env):
        with patch.dict(os.environ, {**ENV, **env}), patch("httpx.post", return_value=answer("{}")) as post:
            provider_gemini.ask("p", IMAGES)
        return post.call_args.kwargs["json"]["generationConfig"]

    def test_unset_means_low_detail_to_save_tokens(self):
        self.assertEqual(self.config_sent({"VISION_IMAGE_DETAIL": ""})["mediaResolution"], "MEDIA_RESOLUTION_LOW")

    def test_default_leaves_the_choice_to_google(self):
        self.assertNotIn("mediaResolution", self.config_sent({"VISION_IMAGE_DETAIL": "default"}))

    def test_levels_are_sent_as_media_resolution(self):
        for level in ("low", "medium", "high"):
            config = self.config_sent({"VISION_IMAGE_DETAIL": level.upper()})  # case does not matter
            self.assertEqual(config["mediaResolution"], f"MEDIA_RESOLUTION_{level.upper()}")

    def test_an_unknown_level_is_refused_before_any_request(self):
        with patch.dict(os.environ, {**ENV, "VISION_IMAGE_DETAIL": "ultra"}), patch("httpx.post") as post,                 self.assertRaises(AiCoreError) as raised:
            provider_gemini.ask("p", IMAGES)
        self.assertEqual(raised.exception.code, "vision_not_configured")
        post.assert_not_called()


class CostSettingsTests(unittest.TestCase):
    config_sent = ImageDetailTests.config_sent

    def test_thinking_is_minimal_unless_set(self):
        self.assertEqual(self.config_sent({"VISION_THINKING": ""})["thinkingConfig"], {"thinkingLevel": "minimal"})

    def test_thinking_levels_are_passed_on(self):
        for level in ("minimal", "low", "medium", "high"):
            self.assertEqual(self.config_sent({"VISION_THINKING": level.upper()})["thinkingConfig"], {"thinkingLevel": level})

    def test_thinking_default_leaves_the_choice_to_google(self):
        self.assertNotIn("thinkingConfig", self.config_sent({"VISION_THINKING": "default"}))

    def test_an_unknown_thinking_level_is_refused_before_any_request(self):
        with patch.dict(os.environ, {**ENV, "VISION_THINKING": "deep"}), patch("httpx.post") as post,                 self.assertRaises(AiCoreError) as raised:
            provider_gemini.ask("p", IMAGES)
        self.assertEqual(raised.exception.code, "vision_not_configured")
        post.assert_not_called()

    def test_every_request_has_an_output_ceiling(self):
        self.assertEqual(self.config_sent({})["maxOutputTokens"], provider_gemini.MAX_OUTPUT_TOKENS)


class RetryTests(unittest.TestCase):
    def ask_with(self, *responses):
        with patch.dict(os.environ, ENV), patch("time.sleep") as sleep, \
                patch("httpx.post", side_effect=list(responses)) as post:
            try:
                return provider_gemini.ask("p", IMAGES), post, sleep
            except AiCoreError as problem:
                return problem, post, sleep

    def test_busy_server_is_retried_and_then_succeeds(self):
        result, post, sleep = self.ask_with(reply(503), reply(503), answer("{}"))
        self.assertEqual(result, "{}")
        self.assertEqual(post.call_count, 3)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [3, 8])

    def test_gives_up_after_three_attempts(self):
        result, post, _ = self.ask_with(reply(503), reply(503), reply(503))
        self.assertEqual(result.code, "vision_error")
        self.assertEqual(post.call_count, 3)

    def test_other_errors_are_not_retried(self):
        result, post, _ = self.ask_with(reply(403))
        self.assertEqual(result.code, "vision_auth")
        self.assertEqual(post.call_count, 1)


class FailureTests(unittest.TestCase):
    def code_for(self, response=None, error=None):
        patcher = patch("httpx.post", return_value=response, side_effect=error)
        with patch.dict(os.environ, ENV), patcher, patch("time.sleep"), self.assertRaises(AiCoreError) as raised:
            provider_gemini.ask("p", IMAGES)
        return raised.exception.code

    def test_bad_key(self):
        self.assertEqual(self.code_for(reply(403)), "vision_auth")

    def test_no_prepaid_credit_left(self):
        self.assertEqual(self.code_for(reply(402)), "vision_no_credit")

    def test_unknown_or_closed_model(self):
        self.assertEqual(self.code_for(reply(404)), "vision_model_unavailable")

    def test_rate_limit(self):
        self.assertEqual(self.code_for(reply(429)), "vision_rate_limited")

    def test_server_error(self):
        self.assertEqual(self.code_for(reply(500)), "vision_error")

    def test_no_connection(self):
        self.assertEqual(self.code_for(error=httpx.ConnectError("down")), "vision_unreachable")

    def test_blocked_prompt(self):
        blocked = reply(json={"promptFeedback": {"blockReason": "SAFETY"}})
        self.assertEqual(self.code_for(blocked), "vision_blocked")

    def test_empty_answer_is_returned_as_empty_text(self):
        with patch.dict(os.environ, ENV), patch("httpx.post", return_value=reply(json={"candidates": []})):
            self.assertEqual(provider_gemini.ask("p", IMAGES), "")


if __name__ == "__main__":
    unittest.main()
