"""Inspectable keyword heuristics; scores are text matches, not visual judgements."""

import re
from urllib.parse import unquote, urlsplit

# Specific asset types take precedence over generic product words.
CATEGORY_WORDS = {
    "logo": {"logo", "logos", "logotype", "wordmark", "emblem"},
    "packaging": {"packaging", "package", "wrapper", "box", "bottle", "carton"},
    "web": {"website", "webpage", "homepage", "screenshot", "landing"},
    "product": {"product", "products", "car", "cars", "automotive", "vehicle", "vehicles", "suv", "sedan", "coupe", "chair", "furniture", "shoe", "shoes", "sneaker", "sneakers", "phone", "phones", "watch", "watches", "lamp", "laptop"},
}


def tokens(text):
    return set(re.findall(r"[^\W_]+", unquote(text).casefold()))


def classify_candidates(candidates, brand, metadata=None):
    metadata = metadata or {}
    brand_tokens = tokens(brand.name)
    category_tokens = tokens(brand.category)
    keyword_groups = [tokens(word) for word in brand.keywords if tokens(word)]
    official = urlsplit(brand.website).hostname if brand.website else None
    if official:
        official = official.casefold().removeprefix("www.")
    for candidate in candidates:
        parsed = urlsplit(candidate.url)
        # URL paths and query values can identify an asset; CDN hostname is not
        # evidence of category or brand. Source domain is scored separately.
        words = tokens(" ".join([metadata.get(candidate.url, ""), parsed.path, parsed.query]))
        candidate.category = "other"
        for category, clues in CATEGORY_WORDS.items():
            if words & clues:
                candidate.category = category
                break
        if not words:
            candidate.relevance = None
            continue
        # Transparent weighted keyword score: brand 50%, category 20%, optional
        # keywords 20%, matching official source 10%. Not a probability or visual fit.
        brand_match = len(words & brand_tokens) / len(brand_tokens) if brand_tokens else 0
        category_match = len(words & category_tokens) / len(category_tokens) if category_tokens else 0
        keyword_match = sum(len(words & group) / len(group) for group in keyword_groups) / len(keyword_groups) if keyword_groups else 0
        host = candidate.source_domain.casefold().removeprefix("www.")
        official_match = bool(official and (host == official or host.endswith("." + official)))
        weights = 0.5 + (0.2 if category_tokens else 0) + (0.2 if keyword_groups else 0) + (0.1 if official else 0)
        score = (0.5 * brand_match + 0.2 * category_match + 0.2 * keyword_match + 0.1 * official_match) / weights
        candidate.relevance = round(score, 3)
        # Relevance does not override review flags or the designer's inclusion choice.
    return candidates
