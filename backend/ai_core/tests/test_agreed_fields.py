"""Tests for the three agreed contract fields: skipped_images and do_dont (extract), coverage (compare)."""

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.ai_core import providers
from backend.ai_core.extract import MAX_IMAGES, MAX_RULES, extract_dna
from backend.ai_core.images import ImageLoadError
from backend.ai_core.scoring import build_compare_result
from backend.ai_core.tests.test_compare import NO_DIRECTIONS, SAMPLE, fake_load, package
from backend.ai_core.tests.test_extract import BRAND, FakeModel, candidate, model_trait
from backend.ai_core.tests.test_scoring import load
from backend.main import app
from contracts.models import CompareResult, TraitScore

RULES = [{"do": "Taper the lamps", "dont": "Round lamps"}, {"do": "One crease", "dont": "Many soft lines"}]


def run(images, answer, load_fn=fake_load):
    return extract_dna(BRAND, images, ask=FakeModel(answer), load=load_fn)


class SkippedImagesTests(unittest.TestCase):
    def test_nothing_is_reported_when_every_image_loads(self):
        result = run([candidate("img_01"), candidate("img_02")], {"traits": [model_trait()]})
        self.assertEqual(result.skipped_images, [])

    def test_an_image_that_cannot_be_downloaded_is_reported_with_the_reason(self):
        def load_fn(image_id, url):
            if image_id == "img_03":
                raise ImageLoadError("could not be downloaded")
            return fake_load(image_id, url)

        images = [candidate("img_01"), candidate("img_02"), candidate("img_03")]
        result = run(images, {"traits": [model_trait()]}, load_fn)
        self.assertEqual([(s.id, s.reason) for s in result.skipped_images], [("img_03", "could not be downloaded")])
        self.assertEqual(len(result.traits), 1)  # the other images still gave a result

    def test_the_reason_comes_from_the_loader(self):
        def load_fn(image_id, url):
            if image_id == "img_03":
                raise ImageLoadError("unsupported file type (image/svg+xml)")
            return fake_load(image_id, url)

        result = run([candidate("img_01"), candidate("img_02"), candidate("img_03")], {"traits": [model_trait()]}, load_fn)
        self.assertEqual(result.skipped_images[0].reason, "unsupported file type (image/svg+xml)")

    def test_images_beyond_the_limit_are_reported_least_relevant_first_cut(self):
        images = [candidate(f"img_{n:02d}", relevance=1 - n / 100) for n in range(MAX_IMAGES + 2)]  # img_00 is the most relevant
        result = run(images, {"traits": [model_trait(evidence_image_ids=["img_00", "img_01"])]})
        self.assertEqual([s.id for s in result.skipped_images], [f"img_{n:02d}" for n in (MAX_IMAGES, MAX_IMAGES + 1)])
        self.assertIn(f"only the {MAX_IMAGES} most relevant", result.skipped_images[0].reason)

    def test_images_the_designer_did_not_select_are_not_reported(self):
        result = run([candidate("img_01"), candidate("img_02"), candidate("img_09", included=False)], {"traits": [model_trait()]})
        self.assertEqual(result.skipped_images, [])


class DoDontTests(unittest.TestCase):
    def test_rules_from_the_model_are_returned(self):
        result = run([candidate("img_01"), candidate("img_02")], {"traits": [model_trait()], "do_dont": RULES})
        self.assertEqual([(r.do, r.dont) for r in result.do_dont], [("Taper the lamps", "Round lamps"), ("One crease", "Many soft lines")])

    def test_a_missing_do_dont_is_an_empty_list_not_an_error(self):
        self.assertEqual(run([candidate("img_01"), candidate("img_02")], {"traits": [model_trait()]}).do_dont, [])

    def test_incomplete_pairs_are_dropped_and_text_is_trimmed(self):
        rules = [{"do": "  Taper the lamps ", "dont": " Round lamps "}, {"do": "Only a do", "dont": ""}, {"do": " ", "dont": "Only a dont"}]
        result = run([candidate("img_01"), candidate("img_02")], {"traits": [model_trait()], "do_dont": rules})
        self.assertEqual([(r.do, r.dont) for r in result.do_dont], [("Taper the lamps", "Round lamps")])

    def test_at_most_the_limit(self):
        rules = [{"do": f"Do {n}", "dont": f"Dont {n}"} for n in range(MAX_RULES + 3)]
        result = run([candidate("img_01"), candidate("img_02")], {"traits": [model_trait()], "do_dont": rules})
        self.assertEqual(len(result.do_dont), MAX_RULES)

    def test_the_prompt_asks_for_rules_backed_by_traits(self):
        model = FakeModel({"traits": [model_trait()]})
        extract_dna(BRAND, [candidate("img_01"), candidate("img_02")], ask=model, load=fake_load)
        self.assertIn("do_dont", model.calls[0][0])
        self.assertIn("backed by a trait", model.calls[0][0])


class CoverageTests(unittest.TestCase):
    def test_the_compare_result_carries_the_coverage(self):
        pkg = package()
        scores = [TraitScore(trait_id=t.id, score=50, status="ok", note="") for t in pkg.traits]
        scores[5] = TraitScore(trait_id="tr_06", score=None, status="not_assessable", note="")
        result = build_compare_result(pkg.traits, scores, [], [], [])
        self.assertEqual(result.coverage, 92)  # 400 of 435

    def test_nothing_judged_is_zero_and_all_importance_zero_is_null(self):
        pkg = package()
        none = [TraitScore(trait_id=t.id, score=None, status="not_assessable", note="") for t in pkg.traits]
        self.assertEqual(build_compare_result(pkg.traits, none, [], [], []).coverage, 0)
        for t in pkg.traits:
            t.importance = 0
        self.assertIsNone(build_compare_result(pkg.traits, none, [], [], []).coverage)

    def test_the_value_follows_the_designers_importance(self):
        pkg = package()
        for trait in pkg.traits[:5]:
            trait.importance = 20
        pkg.traits[5].importance = 100  # the unjudged trait now holds half of the importance (100 of 200)
        scores = [TraitScore(trait_id=t.id, score=50, status="ok", note="") for t in pkg.traits]
        scores[5] = TraitScore(trait_id="tr_06", score=None, status="not_assessable", note="")
        self.assertEqual(build_compare_result(pkg.traits, scores, [], [], []).coverage, 50)


class EndpointTests(unittest.TestCase):
    def test_mock_extract_returns_the_new_fields(self):
        with patch.dict(os.environ, {"MOCK_MODE": "1"}):
            body = TestClient(app).post("/api/dna/extract", json={"brand": BRAND.model_dump(), "images": []}).json()
        self.assertEqual(len(body["do_dont"]), 3)
        self.assertEqual(body["skipped_images"], [{"id": "img_14", "reason": "could not be downloaded"}])

    def test_mock_compare_returns_the_coverage_and_follows_importance(self):
        pkg = load("house_style_package.json")
        body = {"package": pkg, "design_image": "https://example.com/d.png"}
        with patch.dict(os.environ, {"MOCK_MODE": "1"}):
            self.assertEqual(TestClient(app).post("/api/compare", json=body).json()["coverage"], 92)
            for trait in pkg["traits"][:5]:
                trait["importance"] = 20
            pkg["traits"][5]["importance"] = 100  # 100 of 200 is not judged
            self.assertEqual(TestClient(app).post("/api/compare", json=body).json()["coverage"], 50)

    def test_live_extract_and_compare_carry_the_fields(self):
        env = {"MOCK_MODE": "0", "VISION_PROVIDER": "fake", "VISION_API_KEY": "test"}
        images = [candidate("img_01").model_dump(), candidate("img_02").model_dump()]
        extract_model = FakeModel({"traits": [model_trait()], "do_dont": RULES})
        with patch.dict(os.environ, env), patch.dict(providers.PROVIDERS, {"fake": extract_model}), \
                patch("backend.ai_core.extract.load_image", fake_load):
            response = TestClient(app).post("/api/dna/extract", json={"brand": BRAND.model_dump(), "images": images})
        self.assertEqual(len(response.json()["do_dont"]), 2)
        self.assertEqual(response.json()["skipped_images"], [])

        compare_model = FakeModel(SAMPLE, NO_DIRECTIONS)
        body = {"package": load("house_style_package.json"), "design_image": "https://example.com/d.png"}
        with patch.dict(os.environ, env), patch.dict(providers.PROVIDERS, {"fake": compare_model}), \
                patch("backend.ai_core.compare.load_image", fake_load):
            result = TestClient(app).post("/api/compare", json=body).json()
        self.assertEqual(result["coverage"], 92)
        self.assertIsInstance(CompareResult(**result).coverage, int)


if __name__ == "__main__":
    unittest.main()
