"""Filter using available metadata; do not download images or guess dimensions."""

from urllib.parse import urlsplit, urlunsplit

from .serpapi import SearchError

MIN_SIDE = 128


def positive_dimension(value):
    # Only explicit positive pixel dimensions count, never percentages or zero.
    if isinstance(value, bool):
        return None
    try:
        text = str(value).strip()
        if not text.isdigit():
            return None
        number = int(text)
        return number if number > 0 else None
    except (ValueError, TypeError):
        return None


def image_key(url):
    parsed = urlsplit(url)
    # Fragments do not identify a different downloaded resource. Keep query strings:
    # CDN parameters may choose a different image, crop or resolution.
    host = parsed.hostname.lower()
    port = parsed.port
    if ":" in host:
        host = "[" + host + "]"
    if port and not (parsed.scheme.lower() == "https" and port == 443 or parsed.scheme.lower() == "http" and port == 80):
        host += ":" + str(port)
    return urlunsplit((parsed.scheme.lower(), host, parsed.path or "/", parsed.query, ""))


def filter_candidates(candidates, dimensions=None):
    dimensions = dimensions or {}
    kept, seen = [], set()
    for candidate in candidates:
        width, height = dimensions.get(candidate.url, (None, None))
        # Unknown dimensions are not evidence that an image is tiny.
        if any(value is not None and value < MIN_SIDE for value in (width, height)):
            continue
        key = image_key(candidate.url)
        if key in seen:
            continue
        seen.add(key)
        kept.append(candidate)
    if not kept:
        raise SearchError(404, "no_usable_images", "No usable images remain after filtering — try a different product page or search keywords.")
    return kept
