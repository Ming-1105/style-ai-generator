"""Load the image behind an ImageCandidate so it can be sent to a vision model.

Images are downloaded into memory for one request and never written to disk
(AGENTS.md: scraped images are used transiently for analysis).
"""

import base64
from dataclasses import dataclass

import httpx

SUPPORTED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_BYTES = 5 * 1024 * 1024
TIMEOUT_SECONDS = 10


@dataclass
class LoadedImage:
    id: str          # the ImageCandidate id, e.g. "img_01"
    media_type: str  # e.g. "image/jpeg"
    data: bytes


class ImageLoadError(Exception):
    """Why one image could not be used. The message is short and human-readable."""


def load_image(image_id: str, url: str) -> LoadedImage:
    if url.startswith("data:"):
        media_type, data = _read_data_url(url)
    elif url.startswith(("http://", "https://")):
        media_type, data = _download(url)
    else:
        raise ImageLoadError("not a web address")

    if media_type not in SUPPORTED_TYPES:
        raise ImageLoadError(f"unsupported file type ({media_type or 'unknown'})")
    if len(data) > MAX_BYTES:
        raise ImageLoadError("file is larger than 5 MB")
    return LoadedImage(id=image_id, media_type=media_type, data=data)


def _read_data_url(url: str) -> tuple[str, bytes]:
    header, _, payload = url.partition(",")
    if not header.endswith(";base64"):
        raise ImageLoadError("data URL is not base64-encoded")
    media_type = header[len("data:"):-len(";base64")]
    try:
        return media_type, base64.b64decode(payload, validate=True)
    except ValueError:
        raise ImageLoadError("data URL could not be decoded")


def _download(url: str) -> tuple[str, bytes]:
    try:
        response = httpx.get(url, timeout=TIMEOUT_SECONDS, follow_redirects=True)
    except httpx.HTTPError:
        raise ImageLoadError("could not be downloaded")
    if response.status_code >= 400:
        raise ImageLoadError(f"website answered with error {response.status_code}")
    media_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    return media_type, response.content
