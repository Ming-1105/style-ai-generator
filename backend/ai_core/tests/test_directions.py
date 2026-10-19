"""Unit tests for suggested directions. The model is faked: no key, no network.

Run from the repo root:  python -m unittest discover -s backend/ai_core/tests -t .
"""

import unittest

from backend.ai_core.compare import compare_design
from backend.ai_core.directions import MAX_DIRECTIONS, generate_directions, pick_gap_traits
from backend.ai_core.errors import AiCoreError
from backend.ai_core.images import LoadedImage
from backend.ai_core.tests.test_compare import SAMPLE, DESIGN, fake_load, package
from backend.ai_core.tests.test_extract import FakeModel
from contracts.models import TraitScore

DESIGN_IMAGE = LoadedImage("design", "image/png", b"x")


def scores_of(pkg) -> list[TraitScore]:
    """The sample judgements as TraitScores (tr_01 31, tr_02 48, tr_03 88, tr_04 74, tr_05 66, tr_06 not assessable)."""
    return [TraitScore(trait_id=j["trait_id"], score=j["score"], status=j["status"], note=j["note"]) for j in SAMPLE["traits"]]


def direction(title, *trait_ids, rationale="Change this."):
    return {"title": title, "rationale": rationale, "trait_ids": list(trait_ids)}


class PickGapTraitsTests(unittest.TestCase):
    def test_biggest_gaps_first_and_at_most_three(self):
        pkg = package()
        picked = pick_gap_traits(pkg.traits, scores_of(pkg))
        # gaps: tr_01 6210, tr_02 4160, tr_05 2380 (tr_04 1690 and tr_03 1140 are smaller)
        self.assertEqual([(t.id, gap) for t, _, gap in picked], [("tr_01", 6210), ("tr_02", 4160), ("tr_05", 2380)])

    def test_importance_zero_is_never_picked(self):
        pkg = package()
        pkg.traits[0].importance = 0
        self.assertNotIn("tr_01", [t.id for t, _, _ in pick_gap_traits(pkg.traits, scores_of(pkg))])

    def test_not_assessable_traits_are_never_picked(self):
        pkg = package()
        picked = [t.id for t, _, _ in pick_gap_traits(pkg.traits, scores_of(pkg))]
        self.assertNotIn("tr_06", picked)


class GenerateDirectionsTests(unittest.TestCase):
    def generate(self, answer, pkg=None):
        pkg = pkg or package()
        model = FakeModel(answer)
        result = generate_directions(model, pkg.brand.name, [DESIGN_IMAGE], pkg.traits, scores_of(pkg))
        return result, model

    def test_directions_are_ordered_by_gap_and_get_letters_in_that_order(self):
        result, _ = self.generate({"directions": [
            direction("Centre the stripe", "tr_02"),
            direction("Sharpen the lamps", "tr_01"),
            direction("Calm the colour", "tr_05"),
        ]})
        self.assertEqual([(d.id, d.title, d.trait_ids) for d in result], [
            ("dir_a", "Sharpen the lamps", ["tr_01"]),
            ("dir_b", "Centre the stripe", ["tr_02"]),
            ("dir_c", "Calm the colour", ["tr_05"]),
        ])
        self.assertTrue(all(d.image_url is None for d in result))

    def test_a_direction_with_no_trait_we_sent_is_dropped(self):
        result, _ = self.generate({"directions": [
            direction("Sharpen the lamps", "tr_01"),
            direction("Invent something", "tr_99"),
            direction("Fix the overhang", "tr_06"),  # not a gap trait: not shown to the model
            direction("No trait at all"),
        ]})
        self.assertEqual([d.title for d in result], ["Sharpen the lamps"])

    def test_trait_ids_outside_the_gaps_are_removed_from_a_direction(self):
        result, _ = self.generate({"directions": [direction("Sharpen the lamps", "tr_01", "tr_03", "tr_01")]})
        self.assertEqual(result[0].trait_ids, ["tr_01"])

    def test_at_most_three(self):
        many = {"directions": [direction(f"Try {n}", "tr_01") for n in range(6)]}
        self.assertEqual(len(self.generate(many)[0]), MAX_DIRECTIONS)

    def test_a_direction_covering_two_traits_ranks_by_its_biggest_gap(self):
        result, _ = self.generate({"directions": [direction("Calm the colour", "tr_05"), direction("Rework front", "tr_02", "tr_05")]})
        self.assertEqual([d.title for d in result], ["Rework front", "Calm the colour"])  # 4160 beats 2380

    def test_no_gap_means_no_request(self):
        pkg = package()
        perfect = [TraitScore(trait_id=t.id, score=100, status="ok", note="") for t in pkg.traits]
        model = FakeModel()
        self.assertEqual(generate_directions(model, "x", [DESIGN_IMAGE], pkg.traits, perfect), [])
        self.assertEqual(model.calls, [])

    def test_prompt_shows_traits_scores_and_notes_but_never_importance(self):
        _, model = self.generate({"directions": []})
        prompt = model.calls[0][0]
        self.assertIn("tr_01 | Blade headlights", prompt)
        self.assertIn("scored 31", prompt)
        self.assertIn("observed: Lamps are round.", prompt)
        self.assertNotIn("tr_06", prompt)       # not assessable: not a gap
        self.assertNotIn("importance", prompt.lower())
        self.assertNotIn("{{", prompt)
        self.assertEqual(model.calls[0][1], ["design"])

    def test_unreadable_answer_is_retried_once_then_reported(self):
        pkg = package()
        model = FakeModel("nope", "still nope")
        with self.assertRaises(AiCoreError) as raised:
            generate_directions(model, "x", [DESIGN_IMAGE], pkg.traits, scores_of(pkg))
        self.assertEqual(raised.exception.code, "invalid_model_output")
        self.assertEqual(len(model.calls), 2)


class InsideCompareTests(unittest.TestCase):
    def test_compare_returns_the_directions_in_gap_order(self):
        model = FakeModel(SAMPLE, {"directions": [direction("Centre the stripe", "tr_02"), direction("Sharpen the lamps", "tr_01")]})
        result = compare_design(package(), DESIGN, ask=model, load=fake_load)
        self.assertEqual([d.title for d in result.directions], ["Sharpen the lamps", "Centre the stripe"])
        self.assertEqual(len(model.calls), 2)

    def test_importance_zero_trait_gets_no_direction(self):
        pkg = package()
        pkg.traits[0].importance = 0
        model = FakeModel(SAMPLE, {"directions": [direction("Sharpen the lamps", "tr_01"), direction("Centre the stripe", "tr_02")]})
        result = compare_design(pkg, DESIGN, ask=model, load=fake_load)
        self.assertEqual([d.title for d in result.directions], ["Centre the stripe"])

    def test_failed_directions_do_not_lose_the_scores(self):
        model = FakeModel(SAMPLE, "nope", "still nope")
        result = compare_design(package(), DESIGN, ask=model, load=fake_load)
        self.assertEqual(result.overall_fit, 61)
        self.assertEqual(result.directions, [])


if __name__ == "__main__":
    unittest.main()
