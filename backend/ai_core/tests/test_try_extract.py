import base64
import tempfile
import unittest
from pathlib import Path

from backend.ai_core.images import load_image
from backend.ai_core.try_extract import build_candidates


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


if __name__ == "__main__":
    unittest.main()
