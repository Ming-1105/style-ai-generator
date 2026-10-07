import unittest

from contracts.models import Brand
from .flagging import flag_candidates
from .test_filtering import candidate


class FlaggingTests(unittest.TestCase):
    def flag(self, image, size=None, text="", website="https://vorden.example"):
        return flag_candidates([image], Brand(name="Vorden", website=website), {image.url:size} if size else {}, {image.url:text})[0]

    def test_low_resolution_excluded_with_reason(self):
        image = self.flag(candidate("https://cdn.example/car"), (400,300))
        self.assertTrue(image.flagged)
        self.assertFalse(image.included)
        self.assertIn("400 × 300", image.flag_reason)

    def test_unknown_size_and_official_domain_not_flagged(self):
        image = self.flag(candidate("https://cdn.example/car"))
        self.assertFalse(image.flagged)
        self.assertTrue(image.included)
        self.assertIsNone(image.flag_reason)

    def test_third_party_is_uncertain_not_accused(self):
        image = candidate("https://cdn.example/car")
        image.source_domain = "magazine.example"
        self.flag(image)
        self.assertIn("may be third-party", image.flag_reason)
        self.assertFalse(image.included)

    def test_domain_suffix_spoofing_is_flagged(self):
        for host, expected in [("press.vorden.example",False),("vorden.example.evil.test",True),("notvorden.example",True)]:
            image = candidate("https://cdn.example/car")
            image.source_domain=host
            self.assertEqual(self.flag(image).flagged,expected)

    def test_brand_token_fallback(self):
        for host, expected in [("vorden-auto.example",False),("notvorden.example",True)]:
            image=candidate("https://cdn.example/car")
            image.source_domain=host
            self.assertEqual(self.flag(image,website="").flagged,expected)

    def test_render_and_fan_clues_combined_with_size(self):
        image=self.flag(candidate("https://cdn.example/car"),(256,256),"Vorden fan render")
        self.assertIn("Small image",image.flag_reason)
        self.assertIn("render",image.flag_reason)
        self.assertFalse(image.included)

    def test_render_substring_does_not_flag(self):
        self.assertFalse(self.flag(candidate("https://cdn.example/car"),text="Renderingson collection").flagged)

    def test_url_clue(self):
        self.assertTrue(self.flag(candidate("https://cdn.example/fan-art/car.jpg")).flagged)


if __name__ == "__main__":
    unittest.main()
