"""Unit tests for design comparison. The model and the image loading are faked, so these
tests need no API key and no network.

Run from the repo root:  python -m unittest discover -s backend/ai_core/tests -t .
"""

import json
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.ai_core import providers
from backend.ai_core.compare import PROMPT_FILE, compare_design
from backend.ai_core.errors import AiCoreError
from backend.ai_core.images import ImageLoadError, LoadedImage
from backend.ai_core.tests.test_extract import FakeModel
from backend.main import app
from contracts.models import HouseStylePackage
from backend.ai_core.tests.test_scoring import load

DESIGN = "https://example.com/design.png"


def package() -> HouseStylePackage:
    return HouseStylePackage(**load("house_style_package.json"))


def fake_load(image_id: str, url: str) -> LoadedImage:
    return LoadedImage(id=image_id, media_type="image/png", data=b"not a real image")


def judgement(trait_id, score, status="ok", note="note"):
    return {"trait_id": trait_id, "score": score, "status": status, "note": note}


# The Acme sample judgements, as a model would return them.
SAMPLE = {"view": "front view", "traits": [
    judgement("tr_01", 31, note="Lamps are round."),
    judgement("tr_02", 48, note="Stripe is off-centre."),
    judgement("tr_03", 88, note="Crest sits on the hood."),
    judgement("tr_04", 74, note="Shoulder line rises."),
    judgement("tr_05", 66, note="Graphite with one accent."),
    judgement("tr_06", None, "not_assessable", "Needs a side view."),
]}


NO_DIRECTIONS = {"directions": []}  # the second model request (directions): nothing to suggest


def run(answer, pkg=None, load=fake_load):
    model = FakeModel(answer, NO_DIRECTIONS)
    return compare_design(pkg or package(), DESIGN, ask=model, load=load), model


def scores_by_id(result):
    return {s.trait_id: s for s in result.trait_scores}


class ResultFromJudgementsTests(unittest.TestCase):
    def test_sample_judgements_give_the_fixture_numbers(self):
        result, _ = run(SAMPLE)
        self.assertEqual(result.overall_fit, 61)
        self.assertEqual([s.score for s in result.trait_scores], [31, 48, 88, 74, 66, None])
        self.assertEqual(result.trait_scores[5].status, "not_assessable")

    def test_matches_and_departures_come_from_the_notes_and_thresholds(self):
        result, _ = run(SAMPLE)
        self.assertEqual([m.trait_ids for m in result.matches], [["tr_03"], ["tr_04"]])  # 88, 74
        # below 50, plus the one that could not be judged; 66 (tr_05) is in neither list
        self.assertEqual([d.trait_ids for d in result.departures], [["tr_01"], ["tr_02"], ["tr_06"]])
        self.assertEqual(result.departures[0].text, "Lamps are round.")

    def test_thresholds(self):
        for score, listed in ((70, "matches"), (69, None), (50, None), (49, "departures")):
            answer = {"traits": [judgement("tr_01", score)]}
            pkg = package()
            pkg.traits = pkg.traits[:1]
            pkg.traits[0].importance = 50  # keeps the signature rule out of the way
            result, _ = run(answer, pkg)
            self.assertEqual(bool(result.matches), listed == "matches", score)
            self.assertEqual(bool(result.departures), listed == "departures", score)

    def test_no_directions_when_the_model_suggests_none(self):
        self.assertEqual(run(SAMPLE)[0].directions, [])

    def test_a_signature_trait_scoring_low_is_listed_once(self):
        # tr_01: importance 90, score 31. The note-based departure already covers it, so the
        # signature rule (a safeguard that fires below 40) must not add a second one.
        result, _ = run(SAMPLE)
        self.assertEqual(sum(1 for d in result.departures if "tr_01" in d.trait_ids), 1)

    def test_changing_importance_changes_the_fit_but_not_the_judgements(self):
        pkg = package()
        pkg.traits[0].importance = 30
        result, _ = run(SAMPLE, pkg)
        self.assertEqual(result.overall_fit, 66)
        self.assertEqual(scores_by_id(result)["tr_01"].score, 31)


class CheckedInCodeTests(unittest.TestCase):
    def test_not_assessable_never_keeps_a_score(self):
        answer = {"traits": [judgement("tr_01", 80, "not_assessable", "Cannot see.")]}
        score = scores_by_id(run(answer)[0])["tr_01"]
        self.assertEqual((score.score, score.status, score.note), (None, "not_assessable", "Cannot see."))

    def test_ok_without_a_score_becomes_not_assessable(self):
        score = scores_by_id(run({"traits": [judgement("tr_01", None)]})[0])["tr_01"]
        self.assertEqual((score.score, score.status), (None, "not_assessable"))

    def test_a_trait_the_model_skipped_is_not_assessable_never_zero(self):
        result, _ = run({"traits": [judgement("tr_01", 31)]})
        skipped = scores_by_id(result)["tr_02"]
        self.assertEqual((skipped.score, skipped.status), (None, "not_assessable"))
        self.assertEqual(result.overall_fit, 31)  # only the one judged trait counts

    def test_unknown_trait_ids_and_duplicates_are_ignored(self):
        answer = {"traits": [judgement("tr_99", 5), judgement("tr_01", 31), judgement("tr_01", 99)]}
        result, _ = run(answer)
        self.assertNotIn("tr_99", scores_by_id(result))
        self.assertEqual(scores_by_id(result)["tr_01"].score, 31)

    def test_scores_in_package_order_with_one_entry_per_trait(self):
        result, _ = run({"traits": list(reversed(SAMPLE["traits"]))})
        self.assertEqual([s.trait_id for s in result.trait_scores], [f"tr_0{i}" for i in range(1, 7)])

    def test_trait_flagged_low_confidence_at_extraction_stays_flagged(self):
        pkg = package()
        pkg.traits[5].low_confidence = True
        answer = {"traits": [judgement("tr_06", 60)]}
        self.assertEqual(scores_by_id(run(answer, pkg)[0])["tr_06"].status, "low_confidence")

    def test_decimal_scores_are_rounded(self):
        self.assertEqual(scores_by_id(run({"traits": [judgement("tr_01", 71.6)]})[0])["tr_01"].score, 72)


class WhatIsSentTests(unittest.TestCase):
    def test_only_the_design_image_is_sent(self):
        _, model = run(SAMPLE)
        self.assertEqual(model.calls[0][1], ["design"])

    def test_prompt_lists_the_traits_but_never_the_importance(self):
        _, model = run(SAMPLE)
        prompt = model.calls[0][0]
        self.assertIn("tr_01 | Blade headlights: Sharp, tapered LED graphic", prompt)
        self.assertIn("Acme", prompt)
        self.assertNotIn("{{", prompt)
        self.assertNotIn("importance", prompt.lower())
        self.assertNotIn("importance", PROMPT_FILE.read_text(encoding="utf-8").lower())
        for trait in package().traits:  # no importance number next to any trait
            self.assertNotIn(f"importance\": {trait.importance}", prompt)


class HonestFailureTests(unittest.TestCase):
    def test_retries_once_on_invalid_json(self):
        model = FakeModel("Sure! Scores below.", SAMPLE, NO_DIRECTIONS)
        result = compare_design(package(), DESIGN, ask=model, load=fake_load)
        self.assertEqual(result.overall_fit, 61)
        self.assertEqual(len(model.calls), 3)  # unreadable answer, the retry, then the directions

    def test_retries_once_when_a_score_is_out_of_range(self):
        model = FakeModel({"traits": [judgement("tr_01", 150)]}, SAMPLE, NO_DIRECTIONS)
        self.assertEqual(compare_design(package(), DESIGN, ask=model, load=fake_load).overall_fit, 61)

    def test_clear_error_after_two_unusable_answers(self):
        model = FakeModel("nope", "still nope")
        with self.assertRaises(AiCoreError) as raised:
            compare_design(package(), DESIGN, ask=model, load=fake_load)
        self.assertEqual(raised.exception.code, "invalid_model_output")
        self.assertIn("No scores were made up", raised.exception.message)

    def test_error_and_no_model_call_when_the_design_cannot_be_loaded(self):
        def load(image_id, url):
            raise ImageLoadError("could not be downloaded")

        model = FakeModel()
        with self.assertRaises(AiCoreError) as raised:
            compare_design(package(), DESIGN, ask=model, load=load)
        self.assertEqual(raised.exception.code, "design_not_loaded")
        self.assertEqual(model.calls, [])

    def test_error_when_the_package_has_no_traits(self):
        pkg = package()
        pkg.traits = []
        with self.assertRaises(AiCoreError) as raised:
            compare_design(pkg, DESIGN, ask=FakeModel(), load=fake_load)
        self.assertEqual(raised.exception.code, "no_traits")


class EndpointTests(unittest.TestCase):
    def post(self, env: dict):
        body = {"package": load("house_style_package.json"), "design_image": DESIGN}
        with patch.dict(os.environ, env):
            return TestClient(app).post("/api/compare", json=body)

    def test_live_mode_without_a_provider_gives_a_clear_error(self):
        response = self.post({"MOCK_MODE": "0", "VISION_PROVIDER": "", "VISION_API_KEY": ""})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "vision_not_configured")

    def test_live_mode_runs_the_pipeline_with_a_registered_provider(self):
        model = FakeModel(SAMPLE, NO_DIRECTIONS)
        env = {"MOCK_MODE": "0", "VISION_PROVIDER": "fake", "VISION_API_KEY": "test"}
        with patch.dict(providers.PROVIDERS, {"fake": model}), \
                patch("backend.ai_core.compare.load_image", fake_load):
            response = self.post(env)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["overall_fit"], 61)
        self.assertEqual(response.json()["directions"], [])

    def test_a_design_that_cannot_be_loaded_is_a_422(self):
        def load(image_id, url):
            raise ImageLoadError("unsupported file type (image/svg+xml)")

        env = {"MOCK_MODE": "0", "VISION_PROVIDER": "fake", "VISION_API_KEY": "test"}
        with patch.dict(providers.PROVIDERS, {"fake": FakeModel()}), patch("backend.ai_core.compare.load_image", load):
            response = self.post(env)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "design_not_loaded")


if __name__ == "__main__":
    unittest.main()
