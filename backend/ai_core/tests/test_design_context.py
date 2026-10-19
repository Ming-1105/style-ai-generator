"""Tests for what the designer says about the design: sketch or black and white, and a short description.

Run from the repo root:  python -m unittest discover -s backend/ai_core/tests -t .
"""

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.ai_core import providers
from backend.ai_core.compare import MAX_DESCRIPTION_CHARS, compare_design
from backend.ai_core.tests.test_compare import DESIGN, NO_DIRECTIONS, SAMPLE, fake_load, package
from backend.ai_core.tests.test_extract import FakeModel
from backend.ai_core.tests.test_scoring import load
from backend.main import app


def prompt_for(**kwargs):
    model = FakeModel(SAMPLE, NO_DIRECTIONS)
    compare_design(package(), DESIGN, ask=model, load=fake_load, **kwargs)
    return model.calls[0][0]


class PromptTests(unittest.TestCase):
    def test_nothing_is_added_when_the_designer_says_nothing(self):
        prompt = prompt_for()
        self.assertNotIn("sketch or black and white", prompt)
        self.assertNotIn("own description", prompt)
        self.assertNotIn("{{", prompt)

    def test_a_sketch_switches_off_colour_and_material(self):
        prompt = prompt_for(design_is_sketch=True)
        self.assertIn("sketch or black and white", prompt)
        self.assertIn("Do not judge colour", prompt)
        self.assertNotIn("own description", prompt)

    def test_a_sketch_never_lowers_a_score_for_detail_it_does_not_draw(self):
        prompt = prompt_for(design_is_sketch=True)
        self.assertIn("A feature that the sketch does not draw is not", prompt)
        self.assertIn("never lead you to score a trait lower", prompt)

    def test_the_description_is_given_as_information_not_evidence(self):
        prompt = prompt_for(design_description="A compact GT with a long hood")
        self.assertIn('Description: "A compact GT with a long hood"', prompt)
        self.assertIn("It is not evidence", prompt)
        self.assertNotIn("sketch or black and white", prompt)

    def test_the_description_is_one_short_line_without_double_quotes(self):
        prompt = prompt_for(design_description='line one\n\n  line "two"' + " x" * 400)
        description = prompt.split('Description: "')[1].split("\n")[0]
        self.assertLessEqual(len(description), MAX_DESCRIPTION_CHARS + 1)
        self.assertIn("line one line 'two'", prompt)

    def test_a_blank_description_adds_nothing(self):
        self.assertNotIn("own description", prompt_for(design_description="   \n "))


class EndpointTests(unittest.TestCase):
    def test_the_endpoint_passes_both_fields_on(self):
        model = FakeModel(SAMPLE, NO_DIRECTIONS)
        env = {"MOCK_MODE": "0", "VISION_PROVIDER": "fake", "VISION_API_KEY": "test"}
        body = {"package": load("house_style_package.json"), "design_image": "https://example.com/d.png",
                "design_is_sketch": True, "design_description": "A rough side sketch"}
        with patch.dict(os.environ, env), patch.dict(providers.PROVIDERS, {"fake": model}), \
                patch("backend.ai_core.compare.load_image", fake_load):
            response = TestClient(app).post("/api/compare", json=body)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Do not judge colour", model.calls[0][0])
        self.assertIn("A rough side sketch", model.calls[0][0])

    def test_old_requests_without_the_fields_still_work(self):
        with patch.dict(os.environ, {"MOCK_MODE": "1"}):
            body = {"package": load("house_style_package.json"), "design_image": "https://example.com/d.png"}
            self.assertEqual(TestClient(app).post("/api/compare", json=body).status_code, 200)


if __name__ == "__main__":
    unittest.main()
