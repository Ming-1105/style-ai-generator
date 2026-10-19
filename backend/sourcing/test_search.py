"""Run: python -m unittest backend.sourcing.test_search"""
import os
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from backend.main import app
from backend.sourcing.serpapi import build_query
from contracts.models import Brand


class SearchTests(unittest.TestCase):
    def call(self, response=None, mode="0", key="test-key", name="Acme"):
        with patch.dict(os.environ, {"MOCK_MODE": mode, "IMAGE_SEARCH_PROVIDER": "serpapi", "IMAGE_SEARCH_API_KEY": key}):
            with patch("backend.sourcing.serpapi.httpx.Client") as provider:
                if isinstance(response, Exception):
                    provider.return_value.__enter__.return_value.get.side_effect = response
                else:
                    provider.return_value.__enter__.return_value.get.return_value = response
                result = TestClient(app).post("/api/sources/search", json={"brand": {"name": name}})
                return result, provider

    def test_mock_never_calls_provider(self):
        result, provider = self.call(mode="1", key="")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.json()["candidates"]), 18)
        provider.assert_not_called()

    def test_query(self):
        self.assertEqual(build_query(Brand(name="Acme", category="automotive", keywords=["SUV", "electric"])), "Acme automotive SUV electric official")

    def test_query_without_the_word_official(self):
        brand = Brand(name="Volvo", category="automotive")
        self.assertEqual(build_query(brand), "Volvo automotive official")
        self.assertEqual(build_query(brand, official=False), "Volvo automotive")

    def test_searches_again_without_official_when_google_returns_nothing(self):
        empty = httpx.Response(200, json={"error": "Google hasn't returned any results for this query."})
        found = httpx.Response(200, json={"images_results": [
            {"original": "https://cdn.example/car.jpg", "link": "https://acme.example/cars", "thumbnail": "https://cdn.example/small.jpg"},
        ]})
        with patch.dict(os.environ, {"MOCK_MODE": "0", "IMAGE_SEARCH_PROVIDER": "serpapi", "IMAGE_SEARCH_API_KEY": "test-key"}):
            with patch("backend.sourcing.serpapi.httpx.Client") as provider:
                get = provider.return_value.__enter__.return_value.get
                get.side_effect = [empty, found]
                result = TestClient(app).post("/api/sources/search", json={"brand": {"name": "Volvo", "category": "automotive"}})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.json()["candidates"]), 1)
        queries = [call.kwargs["params"]["q"] for call in get.call_args_list]
        self.assertEqual(queries, ["Volvo automotive official", "Volvo automotive"])

    def test_does_not_search_twice_when_the_first_search_works_or_fails_for_another_reason(self):
        for response in (httpx.Response(200, json={"images_results": [
                {"original": "https://cdn.example/car.jpg", "link": "https://acme.example/cars"}]}),
                httpx.Response(429, json={}), httpx.Response(401, json={})):
            with self.subTest(status=response.status_code):
                _, provider = self.call(response)
                provider.return_value.__enter__.return_value.get.assert_called_once()

    def test_live_mapping_and_invalid_rows(self):
        response = httpx.Response(200, json={"images_results": [
            {"original": "https://cdn.example/car.jpg", "link": "https://acme.example/cars", "thumbnail": "https://cdn.example/small.jpg"},
            {"original": "javascript:bad", "link": "https://acme.example"},
        ]})
        result, provider = self.call(response)
        self.assertEqual(result.status_code, 200)
        image = result.json()["candidates"][0]
        self.assertEqual(image["source_domain"], "acme.example")
        self.assertEqual(image["relevance"], 0.0)
        self.assertEqual(len(result.json()["candidates"]), 1)
        provider.return_value.__enter__.return_value.get.assert_called_once()

    def test_configuration(self):
        result, provider = self.call(key="")
        self.assertEqual(result.json()["error"]["code"], "missing_api_key")
        provider.assert_not_called()
        result, provider = self.call(name=" ")
        self.assertEqual(result.status_code, 400)
        provider.assert_not_called()

    def test_failures(self):
        for status, body, code in [
            (401, {}, "invalid_api_key"), (429, {}, "quota_reached"),
            (500, {}, "search_failed"), (200, {"images_results": []}, "no_results"),
            (200, {"error": "Your account has run out of searches."}, "quota_reached"),
            (200, {"error": "Google hasn't returned any results for this query."}, "no_results"),
            (200, [], "invalid_search_response"),
        ]:
            with self.subTest(code=code):
                result, _ = self.call(httpx.Response(status, json=body))
                self.assertEqual(result.json()["error"]["code"], code)
                self.assertNotIn("test-key", result.text)
        result, _ = self.call(httpx.TimeoutException("secret test-key"))
        self.assertEqual(result.status_code, 504)
        self.assertNotIn("test-key", result.text)


if __name__ == "__main__":
    unittest.main()
