import unittest

from contracts.models import Brand
from .classification import classify_candidates
from .test_filtering import candidate


class ClassificationTests(unittest.TestCase):
    def classify(self, text, brand=None, url="https://cdn.example/asset"):
        image = candidate(url)
        return classify_candidates([image], brand or Brand(name="Acme",category="automotive"), {url:text})[0]

    def test_categories(self):
        for text, expected in [("Acme car logo","logo"),("Acme shoe packaging","packaging"),("Acme homepage screenshot","web"),("Acme SUV","product"),("Acme abstract shape","other")]:
            self.assertEqual(self.classify(text).category,expected)

    def test_url_and_whole_word_matching(self):
        self.assertEqual(self.classify("",url="https://cdn.example/brand%20logo.jpg").category,"logo")
        self.assertEqual(self.classify("ecological illustration").category,"other")

    def test_score_weights(self):
        brand=Brand(name="Acme",category="automotive",keywords=["electric"],website="https://acme.example")
        self.assertEqual(self.classify("Acme automotive electric",brand).relevance,1.0)
        self.assertEqual(self.classify("Acme",brand).relevance,0.6)
        self.assertEqual(self.classify("unrelated abstract image",Brand(name="Acme")).relevance,0)

    def test_unknown_metadata_and_empty_path(self):
        self.assertIsNone(self.classify("",url="https://cdn.example/").relevance)

    def test_optional_fields_do_not_lower_maximum(self):
        self.assertEqual(self.classify("Acme",Brand(name="Acme")).relevance,1)

    def test_flag_and_inclusion_preserved(self):
        image=candidate("https://cdn.example/logo")
        image.flagged=True; image.included=False; image.flag_reason="Review source"
        classify_candidates([image],Brand(name="Acme"),{image.url:"Acme logo"})
        self.assertFalse(image.included)
        self.assertEqual(image.flag_reason,"Review source")


if __name__ == "__main__":
    unittest.main()
