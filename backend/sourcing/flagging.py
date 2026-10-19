"""Explain metadata-based review flags; these are clues, not authenticity claims."""

import re
from urllib.parse import unquote, urlsplit

LOW_SIDE = 512
UNOFFICIAL = re.compile(r"\b(fan[\s_-]*(?:art|render)|unofficial|render(?:ing)?|cgi)\b", re.I)


def flag_candidates(candidates, brand, dimensions=None, metadata=None):
    dimensions, metadata = dimensions or {}, metadata or {}
    official_host = urlsplit(brand.website).hostname if brand.website else None
    if official_host:
        official_host = official_host.lower().removeprefix("www.")
    brand_words = re.findall(r"[^\W_]+", brand.name.lower())
    for candidate in candidates:
        reasons = []
        width, height = dimensions.get(candidate.url, (None, None))
        # 128px tiny images were removed already; smaller references merit review.
        # HTML dimensions are declared display sizes, not verified original sizes.
        if any(side is not None and side < LOW_SIDE for side in (width, height)):
            size = f"{width if width is not None else '?'} × {height if height is not None else '?'}"
            reasons.append(f"Small image dimensions reported ({size} px) — review image quality")
        host = candidate.source_domain.lower().removeprefix("www.")
        matches_official = official_host and (host == official_host or host.endswith("." + official_host))
        # Token matching avoids treating 'notvorden' as the Vorden brand. When an
        # official URL is supplied, prefer exact host/subdomain matching instead.
        host_words = re.findall(r"[^\W_]+", host)
        matches_name = bool(brand_words) and all(word in host_words for word in brand_words)
        if not matches_official and (official_host or not matches_name):
            reasons.append("Source domain does not match the supplied official website — may be third-party coverage or a different company" if official_host else "Source domain does not match the brand name — may be third-party coverage or a different company")
        # Explicit title/alt/URL clues only. An official render is still worth
        # reviewing, but a render clue does not prove that it is fan-made.
        text = " ".join([metadata.get(candidate.url, ""), unquote(candidate.url)])
        if UNOFFICIAL.search(text):
            reasons.append("Title, alt text or URL mentions fan art, unofficial work or a render — review whether it represents the brand")
        if reasons:
            candidate.flagged = True
            candidate.flag_reason = "; ".join(reasons)
            candidate.included = False
    return candidates
