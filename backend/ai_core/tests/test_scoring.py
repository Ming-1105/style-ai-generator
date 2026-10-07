"""Unit tests for the scoring rules, based on the Vorden fixture numbers.

Run from the repo root:  python -m unittest discover -s backend/ai_core/tests -t .
"""

import json
import os
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.ai_core.scoring import (
    build_compare_result,
    overall_fit,
    rank_gaps,
    signature_departures,
)
from backend.main import app
from contracts.models import CompareResult, HouseStylePackage, Trait, TraitScore

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def trait(id: str, importance: int) -> Trait:
    return Trait(id=id, name=id, description="", importance=importance, origin="ai")


def score(id: str, value, status: str = "ok") -> TraitScore:
    return TraitScore(trait_id=id, score=value, status=status)


class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.package = HouseStylePackage(**load("house_style_package.json"))
        self.compare = CompareResult(**load("compare.json"))
        self.traits = self.package.traits
        self.scores = self.compare.trait_scores

    def set_importance(self, trait_id: str, value: int):
        next(t for t in self.traits if t.id == trait_id).importance = value


class OverallFitTests(FixtureCase):
    def test_fixture_gives_61(self):
        # (31×90 + 48×80 + 88×95 + 74×65 + 66×70) / (90+80+95+65+70) = 24420 / 400 = 61.05
        self.assertEqual(overall_fit(self.traits, self.scores), 61)

    def test_not_assessable_is_left_out_not_counted_as_zero(self):
        # Counting tr_06 (importance 35) as 0 would give 24420 / 435 = 56.
        self.assertEqual(self.scores[5].status, "not_assessable")
        self.assertNotEqual(overall_fit(self.traits, self.scores), 56)

    def test_changing_importance_changes_the_result(self):
        self.set_importance("tr_01", 30)  # 22560 / 340 = 66.35
        self.assertEqual(overall_fit(self.traits, self.scores), 66)

    def test_low_confidence_scores_still_count(self):
        traits = [trait("a", 50), trait("b", 50)]
        scores = [score("a", 80), score("b", 40, "low_confidence")]
        self.assertEqual(overall_fit(traits, scores), 60)

    def test_none_when_nothing_could_be_assessed(self):
        traits = [trait("a", 50)]
        self.assertIsNone(overall_fit(traits, [score("a", None, "not_assessable")]))
        self.assertIsNone(overall_fit(traits, []))

    def test_none_when_all_importance_is_zero(self):
        self.assertIsNone(overall_fit([trait("a", 0)], [score("a", 70)]))


class GapRankingTests(FixtureCase):
    def test_fixture_order(self):
        self.assertEqual(rank_gaps(self.traits, self.scores), [
            ("tr_01", 6210),  # 90 × 69
            ("tr_02", 4160),  # 80 × 52
            ("tr_05", 2380),  # 70 × 34
            ("tr_04", 1690),  # 65 × 26
            ("tr_03", 1140),  # 95 × 12
        ])

    def test_importance_zero_never_ranks(self):
        self.set_importance("tr_01", 0)
        self.assertNotIn("tr_01", dict(rank_gaps(self.traits, self.scores)))

    def test_not_assessable_never_ranks(self):
        self.assertNotIn("tr_06", dict(rank_gaps(self.traits, self.scores)))


class SignatureRuleTests(FixtureCase):
    def test_fixture_flags_only_blade_headlights(self):
        found = signature_departures(self.traits, self.scores)
        self.assertEqual([f.trait_ids for f in found], [["tr_01"]])

    def test_thresholds(self):
        cases = [  # (importance, score, flagged?)
            (80, 39, True),
            (80, 40, False),
            (79, 39, False),
        ]
        for importance, value, flagged in cases:
            found = signature_departures([trait("a", importance)], [score("a", value)])
            self.assertEqual(bool(found), flagged, (importance, value))

    def test_applies_whatever_the_overall_fit(self):
        traits = [trait("sig", 80), trait("rest", 100)]
        scores = [score("sig", 10), score("rest", 100)]
        result = build_compare_result(traits, scores, [], [], [])
        self.assertEqual(result.overall_fit, 60)
        self.assertEqual([d.trait_ids for d in result.departures], [["sig"]])


class BuildCompareResultTests(FixtureCase):
    def build(self) -> CompareResult:
        c = self.compare
        return build_compare_result(self.traits, c.trait_scores, c.matches, c.departures, c.directions)

    def test_unchanged_package_reproduces_the_fixture(self):
        self.assertEqual(self.build(), self.compare)

    def test_directions_follow_the_gap_ranking(self):
        self.set_importance("tr_01", 30)  # gap 30 × 69 = 2070, now below tr_02's 4160
        self.assertEqual([d.id for d in self.build().directions], ["dir_b", "dir_a", "dir_c"])

    def test_importance_zero_drops_the_direction(self):
        self.set_importance("tr_01", 0)
        self.assertEqual([d.id for d in self.build().directions], ["dir_b", "dir_c"])

    def test_removed_trait_disappears_from_the_result(self):
        self.traits[:] = [t for t in self.traits if t.id != "tr_02"]
        result = self.build()
        self.assertNotIn("tr_02", [s.trait_id for s in result.trait_scores])
        self.assertNotIn("dir_b", [d.id for d in result.directions])
        self.assertFalse(any("tr_02" in d.trait_ids for d in result.departures))

    def test_trait_without_a_judgement_is_not_assessable(self):
        self.traits.append(Trait(id="tr_07", name="Manual", description="", importance=100, origin="manual"))
        result = self.build()
        added = next(s for s in result.trait_scores if s.trait_id == "tr_07")
        self.assertEqual((added.score, added.status), (None, "not_assessable"))
        self.assertEqual(result.overall_fit, 61)  # left out, not counted as 0


class MockCompareEndpointTests(unittest.TestCase):
    def setUp(self):
        os.environ["MOCK_MODE"] = "1"
        self.client = TestClient(app)
        self.package = load("house_style_package.json")

    def post(self) -> dict:
        body = {"package": self.package, "design_image": "https://vorden-auto.example/design.png"}
        response = self.client.post("/api/compare", json=body)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_fixture_package_returns_the_fixture(self):
        self.assertEqual(self.post(), load("compare.json"))

    def test_changing_importance_changes_the_response(self):
        self.package["traits"][0]["importance"] = 30
        result = self.post()
        self.assertEqual(result["overall_fit"], 66)
        self.assertEqual(result["directions"][0]["id"], "dir_b")


if __name__ == "__main__":
    unittest.main()
