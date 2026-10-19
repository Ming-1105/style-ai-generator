"""Unit tests for trait extraction. The model and the downloads are faked, so these
tests need no API key and no network.

Run from the repo root:  python -m unittest discover -s backend/ai_core/tests -t .
"""

import base64
import json
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.ai_core import providers
from backend.ai_core.errors import AiCoreError
from backend.ai_core.extract import extract_dna
from backend.ai_core.images import ImageLoadError, LoadedImage, load_image
from backend.main import app
from contracts.models import Brand, ImageCandidate

BRAND = Brand(name="Acme", category="automotive", keywords=["GT", "crest"], values="Precise.")


def candidate(id: str, included: bool = True, relevance: float = 0.9) -> ImageCandidate:
    return ImageCandidate(
        id=id, url=f"https://acme-auto.example/{id}.jpg", thumbnail_url="",
        source_domain="acme-auto.example", source_type="scrape", category="product",
        relevance=relevance, included=included,
    )


def fake_load(image_id: str, url: str) -> LoadedImage:
    return LoadedImage(id=image_id, media_type="image/jpeg", data=b"not a real image")


def model_trait(**changes) -> dict:
    trait = {"name": "Blade headlights", "description": "Tapered lamps.",
             "evidence_image_ids": ["img_01", "img_02"], "confidence": 0.9, "importance": 80}
    return {**trait, **changes}


class FakeModel:
    """Stands in for a vision provider: returns the prepared answers one after another."""

    def __init__(self, *answers):
        self.answers = [a if isinstance(a, str) else json.dumps(a) for a in answers]
        self.calls = []  # (prompt, image ids) per call

    def __call__(self, prompt, images):
        self.calls.append((prompt, [image.id for image in images]))
        return self.answers[len(self.calls) - 1]


IMAGES = [candidate("img_01"), candidate("img_02"), candidate("img_03")]


def run(model, images=IMAGES, load=fake_load):
    return extract_dna(BRAND, images, ask=model, load=load)


class CheckedInCodeTests(unittest.TestCase):
    def test_seen_count_is_counted_from_evidence_not_claimed_by_the_model(self):
        model = FakeModel({"traits": [model_trait(seen_count=99)]})
        self.assertEqual(run(model).traits[0].seen_count, 2)

    def test_evidence_for_images_that_were_not_sent_is_dropped(self):
        model = FakeModel({"traits": [model_trait(evidence_image_ids=["img_01", "img_77", "img_01"])]})
        trait = run(model).traits[0]
        self.assertEqual(trait.evidence_image_ids, ["img_01"])
        self.assertEqual(trait.seen_count, 1)

    def test_trait_without_any_valid_evidence_is_removed(self):
        model = FakeModel({"traits": [
            model_trait(name="Invented", evidence_image_ids=["img_77"]),
            model_trait(name="Real"),
        ]})
        traits = run(model).traits
        self.assertEqual([(t.id, t.name) for t in traits], [("tr_01", "Real")])

    def test_low_confidence_below_0_6(self):
        model = FakeModel({"traits": [model_trait(confidence=0.59), model_trait(confidence=0.6)]})
        self.assertEqual([t.low_confidence for t in run(model).traits], [True, False])

    def test_traits_are_marked_as_ai_and_keep_tone_words_and_colors(self):
        model = FakeModel({"traits": [model_trait()], "tone_words": ["Precise"],
                           "colors": [{"name": "Graphite", "hex": "#2B2F33"}]})
        result = run(model)
        self.assertEqual(result.traits[0].origin, "ai")
        self.assertEqual(result.tone_words, ["Precise"])
        self.assertEqual(result.colors[0].hex, "#2B2F33")

    def test_an_empty_trait_list_is_a_valid_answer(self):
        self.assertEqual(run(FakeModel({"traits": []})).traits, [])


class WhatIsSentTests(unittest.TestCase):
    def test_only_included_images_are_sent(self):
        model = FakeModel({"traits": []})
        run(model, images=IMAGES + [candidate("img_09", included=False)])
        self.assertEqual(model.calls[0][1], ["img_01", "img_02", "img_03"])

    def test_prompt_contains_the_brand_and_the_image_ids(self):
        model = FakeModel({"traits": []})
        run(model)
        prompt = model.calls[0][0]
        for expected in ("Acme", "automotive", "GT, crest", "img_01, img_02, img_03"):
            self.assertIn(expected, prompt)
        self.assertNotIn("{{", prompt)

    def test_images_that_fail_to_load_are_skipped(self):
        def load(image_id, url):
            if image_id == "img_02":
                raise ImageLoadError("could not be downloaded")
            return fake_load(image_id, url)

        model = FakeModel({"traits": [model_trait()]})
        trait = run(model, load=load).traits[0]
        self.assertEqual(model.calls[0][1], ["img_01", "img_03"])
        self.assertEqual(trait.evidence_image_ids, ["img_01"])  # img_02 was never seen


class HonestFailureTests(unittest.TestCase):
    def test_retries_once_on_invalid_json(self):
        model = FakeModel("Sure! Here are the traits.", {"traits": [model_trait()]})
        self.assertEqual(len(run(model).traits), 1)
        self.assertEqual(len(model.calls), 2)
        self.assertIn("could not be read", model.calls[1][0])

    def test_retries_once_when_the_shape_is_wrong(self):
        model = FakeModel({"traits": [model_trait(confidence=7)]}, {"traits": [model_trait()]})
        self.assertEqual(len(run(model).traits), 1)

    def test_clear_error_after_two_unusable_answers(self):
        model = FakeModel("nope", "still nope")
        with self.assertRaises(AiCoreError) as raised:
            run(model)
        self.assertEqual(raised.exception.code, "invalid_model_output")
        self.assertEqual(len(model.calls), 2)

    def test_json_wrapped_in_extra_text_is_still_read(self):
        model = FakeModel("```json\n" + json.dumps({"traits": [model_trait()]}) + "\n```")
        self.assertEqual(len(run(model).traits), 1)

    def test_error_when_no_image_is_included(self):
        with self.assertRaises(AiCoreError) as raised:
            run(FakeModel(), images=[candidate("img_01", included=False)])
        self.assertEqual(raised.exception.code, "no_images_selected")

    def test_error_when_fewer_than_two_images_load(self):
        def load(image_id, url):
            if image_id != "img_01":
                raise ImageLoadError("could not be downloaded")
            return fake_load(image_id, url)

        model = FakeModel()
        with self.assertRaises(AiCoreError) as raised:
            run(model, load=load)
        self.assertEqual(raised.exception.code, "too_few_images")
        self.assertEqual(model.calls, [])  # the model is never asked


class LoadImageTests(unittest.TestCase):
    def test_reads_a_data_url(self):
        url = "data:image/png;base64," + base64.b64encode(b"pixels").decode()
        image = load_image("img_01", url)
        self.assertEqual((image.media_type, image.data), ("image/png", b"pixels"))

    def test_rejects_what_a_vision_model_cannot_read(self):
        svg = "data:image/svg+xml;base64," + base64.b64encode(b"<svg/>").decode()
        for url in (svg, "/static/placeholder/img_01.svg", "data:image/png,not-base64"):
            with self.assertRaises(ImageLoadError):
                load_image("img_01", url)


class EndpointTests(unittest.TestCase):
    body = {"brand": BRAND.model_dump(), "images": [c.model_dump() for c in IMAGES]}

    def post(self, env: dict):
        with patch.dict(os.environ, env):
            return TestClient(app).post("/api/dna/extract", json=self.body)

    def test_mock_mode_still_returns_the_fixture(self):
        response = self.post({"MOCK_MODE": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["traits"]), 6)

    def test_live_mode_without_a_provider_gives_a_clear_error(self):
        response = self.post({"MOCK_MODE": "0", "VISION_PROVIDER": "", "VISION_API_KEY": ""})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "vision_not_configured")

    def test_live_mode_runs_the_pipeline_with_a_registered_provider(self):
        model = FakeModel({"traits": [model_trait()]})
        env = {"MOCK_MODE": "0", "VISION_PROVIDER": "fake", "VISION_API_KEY": "test"}
        with patch.dict(providers.PROVIDERS, {"fake": model}), \
                patch("backend.ai_core.extract.load_image", fake_load):
            response = self.post(env)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["traits"][0]["seen_count"], 2)


if __name__ == "__main__":
    unittest.main()
