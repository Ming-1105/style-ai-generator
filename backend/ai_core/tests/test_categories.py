"""Tests for the industrial-design trait categories and the product range.

Run from the repo root:  python -m unittest discover -s backend/ai_core/tests -t .
"""

import unittest

from backend.ai_core.compare import build_prompt as compare_prompt
from backend.ai_core.extract import build_prompt as extract_prompt
from backend.ai_core.extract import clean_category, extract_dna
from backend.ai_core.tests.test_compare import fake_load, package
from backend.ai_core.tests.test_extract import BRAND, FakeModel, candidate, model_trait
from backend.sourcing.serpapi import build_query
from contracts.models import TRAIT_CATEGORIES, Brand, Trait


def extract(traits):
    return extract_dna(BRAND, [candidate("img_01"), candidate("img_02")], ask=FakeModel({"traits": traits}), load=fake_load)


class CategoryTests(unittest.TestCase):
    def test_a_known_category_is_kept(self):
        result = extract([model_trait(category="edges")])
        self.assertEqual(result.traits[0].category, "edges")

    def test_case_and_spaces_do_not_matter(self):
        self.assertEqual(clean_category("  Angles "), "angles")

    def test_an_unknown_or_missing_category_becomes_other(self):
        self.assertEqual(clean_category("vibes"), "other")
        self.assertEqual(clean_category(""), "other")
        self.assertEqual(extract([model_trait()]).traits[0].category, "other")

    def test_the_geometric_categories_exist(self):
        for key in ("form", "proportion", "edges", "angles", "surfaces", "splits", "interfaces", "graphics", "cmf", "other"):
            self.assertIn(key, TRAIT_CATEGORIES)

    def test_old_traits_without_a_category_still_load(self):
        trait = Trait(id="tr_01", name="Old", description="", importance=50, origin="manual")
        self.assertIsNone(trait.category)


class PromptTests(unittest.TestCase):
    def test_extraction_asks_for_categories_and_geometry(self):
        prompt = extract_prompt(BRAND, [fake_load("img_01", "x"), fake_load("img_02", "x")])
        for words in ("`edges`", "`angles`", "`proportion`", "First the geometric traits", "range in degrees", "at most 2 in `graphics`", "logo", "bold colour"):
            self.assertIn(words, prompt)
        self.assertNotIn("{{", prompt)

    def test_the_product_range_is_given_to_the_model(self):
        brand = Brand(name="Acme", product_line="cordless garden tools")
        prompt = extract_prompt(brand, [fake_load("img_01", "x"), fake_load("img_02", "x")])
        self.assertIn("Product range studied: cordless garden tools", prompt)
        self.assertIn("(the brand as a whole)", extract_prompt(Brand(name="Acme"), [fake_load("img_01", "x")]))

    def test_comparison_shows_the_category_and_how_to_judge_it(self):
        prompt = compare_prompt(package(), [fake_load("design", "x")])
        self.assertIn("[Proportions] Short front overhang", prompt)
        self.assertIn("Edges & radii: compare the edge type", prompt)

    def test_a_trait_without_category_is_listed_plainly(self):
        pkg = package()
        pkg.traits[0].category = None
        self.assertIn("- tr_01 | Blade headlights:", compare_prompt(pkg, [fake_load("design", "x")]))


class SearchTests(unittest.TestCase):
    def test_the_product_range_is_part_of_the_search(self):
        brand = Brand(name="Acme", product_line="garden tools", category="tools")
        self.assertEqual(build_query(brand, official=False), "Acme garden tools tools")


if __name__ == "__main__":
    unittest.main()
