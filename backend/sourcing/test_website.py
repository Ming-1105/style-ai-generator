import os
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from backend.main import app
from contracts.models import SearchResponse
from .serpapi import SearchError
from .website import scrape_website

PAGE = "https://vorden.example/products"
PUBLIC_DNS = [(2, 1, 6, "", ("93.184.216.34", 443))]


class WebsiteTests(unittest.TestCase):
    def collect(self, handler):
        real_client = httpx.Client
        with patch("backend.sourcing.website.socket.getaddrinfo", return_value=PUBLIC_DNS):
            with patch("backend.sourcing.website.httpx.Client", side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs)):
                return scrape_website(PAGE)

    def test_collect_only_one_page_without_downloading_images(self):
        requests = []
        def handler(request):
            requests.append(str(request.url))
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text="User-agent: *\nDisallow: /private")
            return httpx.Response(200, headers={"content-type": "text/html"}, text='<img src="/car.jpg"><img src="data:image/png;base64,x" data-src="//cdn.example/logo.png"><a href="/other">Other</a>')
        candidates = self.collect(handler)
        self.assertEqual(requests, ["https://vorden.example/robots.txt", PAGE])
        self.assertEqual([item.url for item in candidates], ["https://vorden.example/car.jpg", "https://cdn.example/logo.png"])
        self.assertTrue(all(item.source_type == "scrape" and item.source_domain == "vorden.example" for item in candidates))

    def test_robots_refusal_never_requests_page(self):
        requests = []
        def handler(request):
            requests.append(str(request.url))
            return httpx.Response(200, text="User-agent: *\nDisallow: /products")
        with self.assertRaises(SearchError) as error:
            self.collect(handler)
        self.assertEqual(error.exception.code, "scraping_disallowed")
        self.assertEqual(len(requests), 1)

    def test_missing_robots_allows_page(self):
        def handler(request):
            if request.url.path == "/robots.txt":
                return httpx.Response(404)
            return httpx.Response(200, headers={"content-type": "text/html"}, text='<base href="/assets/"><img src="car.jpg">')
        self.assertEqual(self.collect(handler)[0].url, "https://vorden.example/assets/car.jpg")

    def test_failures(self):
        cases = [(503, "", "robots_unavailable"), (403, "", "scraping_disallowed"),
                 (302, "", "website_redirect"),
                 (200, "User-agent: *\nCrawl-delay: 10", "website_rate_restricted")]
        for status, text, code in cases:
            with self.subTest(code=code), self.assertRaises(SearchError) as error:
                self.collect(lambda request: httpx.Response(status, text=text))
            self.assertEqual(error.exception.code, code)

    def test_page_redirect_not_followed(self):
        def handler(request):
            return httpx.Response(404) if request.url.path == "/robots.txt" else httpx.Response(302, headers={"location": "/other"})
        with self.assertRaises(SearchError) as error:
            self.collect(handler)
        self.assertEqual(error.exception.code, "website_redirect")

    def test_private_address_rejected(self):
        with patch("backend.sourcing.website.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]):
            with self.assertRaises(SearchError) as error:
                scrape_website("http://localhost/")
            self.assertEqual(error.exception.code, "invalid_website")

    def test_endpoint_combines_sources_and_keeps_mock_isolated(self):
        image = self.collect(lambda request: httpx.Response(404) if request.url.path == "/robots.txt" else httpx.Response(200, headers={"content-type": "text/html"}, text='<img src="/car.jpg">'))
        with patch.dict(os.environ, {"MOCK_MODE": "0"}), patch("backend.sourcing.scrape_website", return_value=image), patch("backend.sourcing.search_images", return_value=SearchResponse(candidates=[])):
            result = TestClient(app).post("/api/sources/search", json={"brand": {"name": "Vorden", "website": PAGE}})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()["candidates"][0]["source_type"], "scrape")
        with patch.dict(os.environ, {"MOCK_MODE": "1"}), patch("backend.sourcing.scrape_website") as scrape:
            result = TestClient(app).post("/api/sources/search", json={"brand": {"name": "Vorden", "website": PAGE}})
            self.assertEqual(len(result.json()["candidates"]), 18)
            scrape.assert_not_called()

    def test_empty_search_can_use_website_but_quota_error_stays_visible(self):
        image = self.collect(lambda request: httpx.Response(404) if request.url.path == "/robots.txt" else httpx.Response(200, headers={"content-type": "text/html"}, text='<img src="/car.jpg">'))
        for code, expected in [("no_results", 200), ("quota_reached", 503)]:
            with patch.dict(os.environ, {"MOCK_MODE": "0"}), patch("backend.sourcing.scrape_website", return_value=image), patch("backend.sourcing.search_images", side_effect=SearchError(503, code, "Search unavailable")):
                result = TestClient(app).post("/api/sources/search", json={"brand": {"name": "Vorden", "website": PAGE}})
                self.assertEqual(result.status_code, expected)


if __name__ == "__main__":
    unittest.main()
