"""Unit tests for reference images in the compare step. The model and the downloads are faked.

Run from the repo root:  python -m unittest discover -s backend/ai_core/tests -t .
"""

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.ai_core import providers
from backend.ai_core.compare import (
    MAX_REFERENCES_PER_TRAIT,
    MAX_REFERENCES_TOTAL,
    compare_design,
    pick_references,
)
from backend.ai_core.images import ImageLoadError
from backend.ai_core.tests.test_compare import DESIGN, NO_DIRECTIONS, SAMPLE, fake_load, package
from backend.ai_core.tests.test_extract import FakeModel
from backend.ai_core.tests.test_scoring import load
from backend.main import app
from contracts.models import ImageCandidate, Trait


def candidates() -> list[ImageCandidate]:
    return [ImageCandidate(**c) for c in load("sources_search.json")["candidates"]]


def run(references, load_fn=fake_load):
    model = FakeModel(SAMPLE, NO_DIRECTIONS)
    result = compare_design(package(), DESIGN, ask=model, load=load_fn, reference_images=references)
    return result, model


class PickReferencesTests(unittest.TestCase):
    def test_up_to_three_per_trait_most_relevant_first(self):
        picked = pick_references(package().traits, candidates())
        # tr_01 cites img_02 (0.94), img_05 (0.93), img_01 (0.96)
        self.assertEqual([c.id for c in picked["tr_01"]], ["img_01", "img_02", "img_05"])
        self.assertTrue(all(len(v) <= MAX_REFERENCES_PER_TRAIT for v in picked.values()))

    def test_ids_that_were_not_sent_are_ignored(self):
        only_one = [c for c in candidates() if c.id == "img_01"]
        picked = pick_references(package().traits, only_one)
        self.assertEqual([c.id for c in picked["tr_01"]], ["img_01"])
        self.assertEqual(picked["tr_04"], [])  # tr_04 cites img_06 and img_17: none were sent

    def test_at_most_twelve_distinct_images_overall(self):
        many = [ImageCandidate(id=f"img_{n:02d}", url=f"https://x.example/{n}.png", thumbnail_url="",
                               source_domain="x.example", source_type="search", category="product", relevance=0.5)
                for n in range(40)]
        traits = [Trait(id=f"tr_{n}", name="t", description="d", importance=50, origin="ai",
                        evidence_image_ids=[f"img_{n * 3 + k:02d}" for k in range(3)]) for n in range(10)]
        picked = pick_references(traits, many)
        distinct = {c.id for images in picked.values() for c in images}
        self.assertEqual(len(distinct), MAX_REFERENCES_TOTAL)
        self.assertEqual(len(picked["tr_0"]), 3)   # early traits are served first
        self.assertEqual(picked["tr_9"], [])       # the cap is reached before the last traits

    def test_an_image_cited_by_several_traits_is_counted_once(self):
        picked = pick_references(package().traits, candidates())
        ids = [c.id for images in picked.values() for c in images]
        self.assertGreater(len(ids), len(set(ids)))  # img_01 is evidence for several traits


class WhatIsSentTests(unittest.TestCase):
    def test_design_first_then_each_reference_once(self):
        _, model = run(candidates())
        sent = model.calls[0][1]
        self.assertEqual(sent[0], "design")
        self.assertEqual(len(sent), len(set(sent)))
        self.assertIn("img_01", sent)
        self.assertLessEqual(len(sent) - 1, MAX_REFERENCES_TOTAL)

    def test_prompt_lists_the_references_under_each_trait_and_explains_them(self):
        _, model = run(candidates())
        prompt = model.calls[0][0]
        self.assertIn("tr_01 | [Interfaces & details] Blade headlights: Sharp, tapered LED graphic that narrows to a point at the outer edge. | reference images: img_01, img_02, img_05", prompt)
        self.assertIn("never score a reference image", prompt)
        self.assertNotIn("importance", prompt.lower())
        self.assertNotIn("{{", prompt)

    def test_without_references_nothing_changes(self):
        for references in (None, []):
            _, model = run(references)
            self.assertEqual(model.calls[0][1], ["design"])
            self.assertNotIn("reference image", model.calls[0][0].lower())

    def test_the_directions_request_only_gets_the_design(self):
        _, model = run(candidates())
        self.assertEqual(model.calls[1][1], ["design"])

    def test_scores_are_still_judged_for_the_design_alone(self):
        result, _ = run(candidates())
        self.assertEqual(result.overall_fit, 61)


class FailureTests(unittest.TestCase):
    def test_a_reference_that_cannot_be_downloaded_is_skipped(self):
        def load_fn(image_id, url):
            if image_id == "img_01":
                raise ImageLoadError("could not be downloaded")
            return fake_load(image_id, url)

        result, model = run(candidates(), load_fn)
        self.assertNotIn("img_01", model.calls[0][1])
        self.assertNotIn("img_01", model.calls[0][0])
        self.assertIn("reference images: img_02, img_05", model.calls[0][0])  # tr_01 keeps the rest
        self.assertEqual(result.overall_fit, 61)

    def test_if_every_reference_fails_it_behaves_as_if_none_were_sent(self):
        def load_fn(image_id, url):
            if image_id == "design":
                return fake_load(image_id, url)
            raise ImageLoadError("could not be downloaded")

        _, model = run(candidates(), load_fn)
        self.assertEqual(model.calls[0][1], ["design"])
        self.assertNotIn("reference image", model.calls[0][0].lower())


class EndpointTests(unittest.TestCase):
    def test_reference_images_in_the_request_reach_the_model(self):
        body = {"package": load("house_style_package.json"), "design_image": DESIGN,
                "reference_images": load("sources_search.json")["candidates"]}
        model = FakeModel(SAMPLE, NO_DIRECTIONS)
        env = {"MOCK_MODE": "0", "VISION_PROVIDER": "fake", "VISION_API_KEY": "test"}
        with patch.dict(os.environ, env), patch.dict(providers.PROVIDERS, {"fake": model}), \
                patch("backend.ai_core.compare.load_image", fake_load):
            response = TestClient(app).post("/api/compare", json=body)
        self.assertEqual(response.status_code, 200)
        self.assertIn("img_01", model.calls[0][1])

    def test_the_field_is_optional(self):
        body = {"package": load("house_style_package.json"), "design_image": DESIGN}
        with patch.dict(os.environ, {"MOCK_MODE": "1"}):
            self.assertEqual(TestClient(app).post("/api/compare", json=body).status_code, 200)


if __name__ == "__main__":
    unittest.main()
