import base64
import tempfile
import unittest
from pathlib import Path

from backend.ai_core.images import load_image
from backend.ai_core.try_extract import build_candidates, group_runs
from contracts.models import Trait


class BuildCandidatesTests(unittest.TestCase):
    def test_files_become_data_urls_the_pipeline_can_load(self):
        with tempfile.TemporaryDirectory() as folder:
            photo = Path(folder) / "photo.png"
            photo.write_bytes(b"pixels")
            candidates = build_candidates([str(photo), "https://example.com/a.jpg"])

        self.assertEqual([c.id for c in candidates], ["img_01", "img_02"])
        image = load_image(candidates[0].id, candidates[0].url)
        self.assertEqual((image.media_type, image.data), ("image/png", b"pixels"))
        self.assertEqual(candidates[1].url, "https://example.com/a.jpg")
        self.assertEqual(candidates[1].source_domain, "example.com")
        self.assertTrue(all(c.included for c in candidates))


def trait(name, *evidence):
    return Trait(id="tr_01", name=name, description="", evidence_image_ids=list(evidence),
                 seen_count=len(evidence), confidence=0.9, importance=50, origin="ai")


class GroupRunsTests(unittest.TestCase):
    def test_traits_are_matched_by_evidence_even_when_the_name_changes(self):
        runs = [
            [trait("Hollow apertures", "img_01", "img_02", "img_03"), trait("Cyclones", "img_07", "img_08")],
            [trait("Toroidal air paths", "img_01", "img_02", "img_04")],
            [trait("Open rings", "img_01", "img_02", "img_03")],
        ]
        groups = group_runs(runs)
        self.assertEqual([len(g["runs"]) for g in groups], [3, 1])
        self.assertEqual(groups[0]["names"], ["Hollow apertures", "Toroidal air paths", "Open rings"])
        self.assertEqual(groups[0]["image_counts"]["img_01"], 3)
        self.assertEqual(groups[0]["image_counts"]["img_04"], 1)

    def test_two_traits_in_one_run_are_never_merged(self):
        groups = group_runs([[trait("A", "img_01", "img_02"), trait("B", "img_01", "img_02")]])
        self.assertEqual(len(groups), 2)


if __name__ == "__main__":
    unittest.main()
