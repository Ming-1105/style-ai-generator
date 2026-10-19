import unittest

import httpx
from unittest.mock import patch

from contracts.models import Brand, ImageCandidate
from .filtering import filter_candidates, positive_dimension
from .serpapi import SearchError, search_images
from .website import PageImages


def candidate(url, source="search"):
    return ImageCandidate(id=url, url=url, thumbnail_url=url, source_domain="acme.example", source_type=source, category="other")


class FilteringTests(unittest.TestCase):
    def test_duplicate_url_across_sources(self):
        first = candidate("https://cdn.example/car.jpg")
        duplicate = candidate(first.url, "scrape")
        self.assertEqual(filter_candidates([first, duplicate]), [first])

    def test_normalization_preserves_image_variants(self):
        urls = ["https://CDN.example:443/car.jpg#one", "https://cdn.example/car.jpg#two", "https://cdn.example/car.jpg?w=800", "https://cdn.example/car.jpg?w=400"]
        self.assertEqual(len(filter_candidates([candidate(url) for url in urls])), 3)

    def test_tiny_threshold_and_unknown_dimensions(self):
        images = [candidate("https://cdn.example/" + name) for name in ("tiny", "boundary", "unknown", "narrow")]
        sizes = {images[0].url:(127,800), images[1].url:(128,128), images[3].url:(None,64)}
        self.assertEqual(filter_candidates(images, sizes), [images[1], images[2]])

    def test_all_tiny_returns_honest_error(self):
        image = candidate("https://cdn.example/tiny")
        with self.assertRaises(SearchError) as error:
            filter_candidates([image], {image.url:(1,1)})
        self.assertEqual(error.exception.code, "no_usable_images")

    def test_dimensions_are_not_guessed(self):
        for value in (None, "50%", "auto", -1, 0, True, "12.5"):
            self.assertIsNone(positive_dimension(value))
        self.assertEqual(positive_dimension(" 128 "), 128)

    def test_provider_original_size_used_instead_of_thumbnail_size(self):
        import os
        sizes = {}
        response = httpx.Response(200,json={"images_results":[{"original":"https://cdn.example/car", "link":"https://acme.example/", "original_width":800,"original_height":600,"thumbnail_width":64,"thumbnail_height":64}]})
        with patch.dict(os.environ,{"IMAGE_SEARCH_PROVIDER":"serpapi","IMAGE_SEARCH_API_KEY":"test"}), patch("backend.sourcing.serpapi.httpx.Client") as client:
            client.return_value.__enter__.return_value.get.return_value = response
            result = search_images(Brand(name="Acme"), dimensions=sizes)
        self.assertEqual(sizes[result.candidates[0].url], (800,600))
        self.assertEqual(len(filter_candidates(result.candidates,sizes)),1)

    def test_html_declared_sizes(self):
        parser = PageImages("https://acme.example/")
        parser.feed('<img src="/tiny" width="32" height="32"><img src="/unknown" width="100%">')
        self.assertEqual(parser.dimensions["https://acme.example/tiny"], (32,32))
        self.assertEqual(parser.dimensions["https://acme.example/unknown"], (None,None))


if __name__ == "__main__":
    unittest.main()
