"""Explain metadata-based review flags; these are clues, not authenticity claims.

An image is flagged (and starts unselected) only when its metadata suggests it is poor quality,
AI-generated, fan-made, or amateur content. Where an image was published is NOT a reason to flag it:
retailers, magazines, press kits and the brand's own site are all normal sources of reference images.
The designer can always tick a flagged image again.
"""

import re
from urllib.parse import unquote

LOW_SIDE = 512

# Words in the title, alt text or URL that point at AI-generated images.
AI_CLUES = re.compile(
    r"\b(?:ai[\s_-]*(?:generated|created|art|image|render)|generated[\s_-]*(?:by|with)[\s_-]*ai|generative[\s_-]*ai"
    r"|midjourney|dall[\s_-]*e|stable[\s_-]*diffusion|chatgpt|firefly)\b", re.I)

# Words that point at fan-made or unofficial images. A plain "render" or "CGI" is not enough: brands
# publish official renders, so those are only flagged when they are also called fan-made or unofficial.
FAN_CLUES = re.compile(
    r"\b(?:fan[\s_-]*(?:art|made|render|edit|concept)|unofficial|concept[\s_-]*art|mock[\s_-]*up|parody)\b", re.I)

# Sites where the photos are made by private people rather than by the brand or a shop or magazine:
# social networks, image boards, art communities and second-hand marketplaces.
USER_CONTENT_SITES = {
    "reddit", "redd", "imgur", "deviantart", "artstation", "flickr", "instagram", "facebook", "fbcdn",
    "tiktok", "tumblr", "craigslist", "marktplaats", "gumtree", "offerup", "vinted", "olx",
    "kleinanzeigen", "mercari",
}


def is_user_content(host: str) -> bool:
    words = re.findall(r"[^\W_]+", host.lower())
    return any(word in USER_CONTENT_SITES or word.startswith("ebay") for word in words)


def flag_candidates(candidates, brand=None, dimensions=None, metadata=None):
    """`brand` is kept so the call stays the same; the source's own name no longer matters."""
    dimensions, metadata = dimensions or {}, metadata or {}
    for candidate in candidates:
        reasons = []
        width, height = dimensions.get(candidate.url, (None, None))
        # 128px tiny images were removed already; smaller references merit review.
        # HTML dimensions are declared display sizes, not verified original sizes.
        if any(side is not None and side < LOW_SIDE for side in (width, height)):
            size = f"{width if width is not None else '?'} × {height if height is not None else '?'}"
            reasons.append(f"Small image dimensions reported ({size} px) — review image quality")
        text = " ".join([metadata.get(candidate.url, ""), unquote(candidate.url)])
        if AI_CLUES.search(text):
            reasons.append("Title, alt text or URL mentions AI-generated work — review whether it shows the real brand")
        if FAN_CLUES.search(text):
            reasons.append("Title, alt text or URL mentions fan art, unofficial work or a mock-up — review whether it represents the brand")
        if is_user_content(candidate.source_domain):
            reasons.append("Source looks like user-generated or marketplace content — review the photo quality and whether it shows the real product")
        if reasons:
            candidate.flagged = True
            candidate.flag_reason = "; ".join(reasons)
            candidate.included = False
    return candidates
