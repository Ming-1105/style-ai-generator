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
        self.assertNotIn("secret-key", post.call_args.args[0])

    def test_model_can_be_overridden(self):
        with patch.dict(os.environ, {**ENV, "VISION_MODEL": "gemini-test"}), \
                patch("httpx.post", return_value=answer("{}")) as post:
            provider_gemini.ask("p", IMAGES)
        self.assertIn("gemini-test:generateContent", post.call_args.args[0])


class FailureTests(unittest.TestCase):
    def code_for(self, response=None, error=None):
        patcher = patch("httpx.post", return_value=response, side_effect=error)
        with patch.dict(os.environ, ENV), patcher, self.assertRaises(AiCoreError) as raised:
            provider_gemini.ask("p", IMAGES)
        return raised.exception.code

    def test_bad_key(self):
        self.assertEqual(self.code_for(reply(403)), "vision_auth")

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
