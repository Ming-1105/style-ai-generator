"""Unit tests for comparing a design that comes as several views. The model and the downloads are faked.

Run from the repo root:  python -m unittest discover -s backend/ai_core/tests -t .
"""

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.ai_core import providers
from backend.ai_core.compare import MAX_DESIGN_IMAGES, compare_design
from backend.ai_core.errors import AiCoreError
from backend.ai_core.images import ImageLoadError
from backend.ai_core.tests.test_compare import DESIGN, NO_DIRECTIONS, SAMPLE, fake_load, package
from backend.ai_core.tests.test_extract import FakeModel
from backend.ai_core.tests.test_references import candidates
from backend.ai_core.tests.test_scoring import load
from backend.main import app

SIDE = "https://example.com/side.png"
BACK = "https://example.com/back.png"


ONE_DIRECTION = {"directions": [{"title": "Sharpen the lamps", "rationale": "Narrow them.", "trait_ids": ["tr_01"]}]}


def run(extra, references=None, load_fn=fake_load):
    model = FakeModel(SAMPLE, ONE_DIRECTION)
    result = compare_design(package(), DESIGN, ask=model, load=load_fn, reference_images=references, additional_design_images=extra)
    return result, model


class WhatIsSentTests(unittest.TestCase):
    def test_all_views_are_sent_in_order_with_their_own_labels(self):
        _, model = run([SIDE, BACK])
        self.assertEqual(model.calls[0][1], ["design", "design_2", "design_3"])

    def test_views_come_before_the_reference_images(self):
        _, model = run([SIDE], references=candidates())
        sent = model.calls[0][1]
        self.assertEqual(sent[:2], ["design", "design_2"])
        self.assertIn("img_01", sent[2:])

    def test_a_single_design_is_sent_as_before(self):
        for extra in (None, []):
            _, model = run(extra)
            self.assertEqual(model.calls[0][1], ["design"])
            self.assertNotIn("different views", model.calls[0][0])

    def test_the_prompt_explains_the_views_only_when_there_are_several(self):
        _, model = run([SIDE, BACK])
        prompt = model.calls[0][0]
        self.assertIn("The design comes as 3 images", prompt)
        self.assertIn('"Image design", "Image design_2", "Image design_3"', prompt)
        self.assertIn("none of the views shows it", prompt)
        self.assertNotIn("{{", prompt)
        self.assertNotIn("importance", prompt.lower())

    def test_the_directions_request_also_sees_every_view(self):
        _, model = run([SIDE, BACK])
        self.assertEqual(model.calls[1][1], ["design", "design_2", "design_3"])

    def test_scores_and_directions_work_as_with_one_view(self):
        result, _ = run([SIDE])
        self.assertEqual(result.overall_fit, 61)
        self.assertEqual([d.title for d in result.directions], ["Sharpen the lamps"])


class LimitsAndFailureTests(unittest.TestCase):
    def test_at_most_four_images_in_total(self):
        compare_design(package(), DESIGN, ask=FakeModel(SAMPLE, NO_DIRECTIONS), load=fake_load,
                       additional_design_images=[SIDE] * (MAX_DESIGN_IMAGES - 1))  # exactly the limit: fine
        model = FakeModel()
        with self.assertRaises(AiCoreError) as raised:
            compare_design(package(), DESIGN, ask=model, load=fake_load, additional_design_images=[SIDE] * MAX_DESIGN_IMAGES)
        self.assertEqual(raised.exception.code, "too_many_design_images")
        self.assertEqual(model.calls, [])

    def test_a_view_that_cannot_be_loaded_is_an_error_naming_it_and_nothing_is_asked(self):
        def load_fn(image_id, url):
            if image_id == "design_2":
                raise ImageLoadError("unsupported file type (image/svg+xml)")
            return fake_load(image_id, url)

        model = FakeModel()
        with self.assertRaises(AiCoreError) as raised:
            compare_design(package(), DESIGN, ask=model, load=load_fn, additional_design_images=[SIDE, BACK])
        self.assertEqual(raised.exception.code, "design_not_loaded")
        self.assertIn("Design image 2 of 3", raised.exception.message)
        self.assertEqual(model.calls, [])

    def test_a_single_design_that_fails_keeps_the_old_wording(self):
        def load_fn(image_id, url):
            raise ImageLoadError("could not be downloaded")

        with self.assertRaises(AiCoreError) as raised:
            compare_design(package(), DESIGN, ask=FakeModel(), load=load_fn)
        self.assertTrue(raised.exception.message.startswith("The design image could not be used"))


class EndpointTests(unittest.TestCase):
    def post(self, extra):
        body = {"package": load("house_style_package.json"), "design_image": DESIGN, "additional_design_images": extra}
        return TestClient(app).post("/api/compare", json=body)

    def test_additional_views_in_the_request_reach_the_model(self):
        model = FakeModel(SAMPLE, NO_DIRECTIONS)
        env = {"MOCK_MODE": "0", "VISION_PROVIDER": "fake", "VISION_API_KEY": "test"}
        with patch.dict(os.environ, env), patch.dict(providers.PROVIDERS, {"fake": model}), \
                patch("backend.ai_core.compare.load_image", fake_load):
            response = self.post([SIDE])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(model.calls[0][1], ["design", "design_2"])

    def test_too_many_views_is_a_422(self):
        env = {"MOCK_MODE": "0", "VISION_PROVIDER": "fake", "VISION_API_KEY": "test"}
        with patch.dict(os.environ, env), patch.dict(providers.PROVIDERS, {"fake": FakeModel()}):
            response = self.post([SIDE] * 4)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "too_many_design_images")

    def test_the_field_is_optional_and_mock_mode_ignores_it(self):
        with patch.dict(os.environ, {"MOCK_MODE": "1"}):
            body = {"package": load("house_style_package.json"), "design_image": DESIGN}
            self.assertEqual(TestClient(app).post("/api/compare", json=body).status_code, 200)
            self.assertEqual(self.post([SIDE, BACK]).status_code, 200)


if __name__ == "__main__":
    unittest.main()
