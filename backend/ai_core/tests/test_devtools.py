import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.ai_core.tests.test_scoring import load


class DevToolsTests(unittest.TestCase):
    def get(self, path: str, env=None):
        with patch.dict(os.environ, env or {}):
            return TestClient(app).get(path)

    def test_compare_page_is_served(self):
        response = self.get("/api/dev/compare")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("Compare test", response.text)

    def test_status_says_mock_mode(self):
        self.assertEqual(self.get("/api/dev/status", {"MOCK_MODE": "1"}).json()["mock_mode"], True)

    def test_status_names_the_live_model_and_never_the_key(self):
        env = {"MOCK_MODE": "0", "VISION_PROVIDER": "gemini", "VISION_MODEL": "gemini-test", "VISION_API_KEY": "secret-key"}
        response = self.get("/api/dev/status", env)
        self.assertEqual(response.json(), {"mock_mode": False, "provider": "gemini", "model": "gemini-test"})
        self.assertNotIn("secret-key", response.text)

    def test_sample_package_is_the_fixture(self):
        self.assertEqual(self.get("/api/dev/sample-package").json(), load("house_style_package.json"))

    def test_dev_routes_are_not_listed_in_the_api_docs(self):
        paths = TestClient(app).get("/openapi.json").json()["paths"]
        self.assertFalse([p for p in paths if p.startswith("/api/dev")])


if __name__ == "__main__":
    unittest.main()
