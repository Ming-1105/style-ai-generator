"""Read robots.txt and one HTML page; never fetch images or crawl links."""

import hashlib
import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx

from contracts.models import ImageCandidate
from .serpapi import SearchError, valid_url

USER_AGENT = "BrandDNAPrototype/1.0"


def public_website(url):
    if not valid_url(url):
        raise SearchError(400, "invalid_website", "Enter a complete official website URL starting with https:// or http://.")
    parsed = urlsplit(url)
    try:
        if parsed.username or parsed.password or parsed.port not in (None, 80, 443):
            raise ValueError()
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses):
            raise ValueError()
    except (ValueError, OSError):
        raise SearchError(400, "invalid_website", "Use a publicly reachable official website, without credentials or a custom port.") from None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))


def read_document(client, url, limit):
    # Do not follow redirects: only the exact supplied page is authorized.
    with client.stream("GET", url) as response:
        if 300 <= response.status_code < 400:
            raise SearchError(422, "website_redirect", "The website redirects — enter its final page URL and try again.")
        content = bytearray()
        for chunk in response.iter_bytes():
            content.extend(chunk)
            if len(content) > limit:
                raise SearchError(422, "website_too_large", "This website page is too large — try a smaller official product page.")
        return response.status_code, response.headers.get("content-type", ""), content.decode(response.encoding or "utf-8", errors="replace")


class PageImages(HTMLParser):
    def __init__(self, page_url):
        super().__init__(convert_charrefs=True)
        self.base_url = page_url
        self.images = []
        self.has_base = False

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "base" and not self.has_base and attrs.get("href"):
            self.base_url = urljoin(self.base_url, attrs["href"])
            self.has_base = True
        if tag != "img" or len(self.images) >= 30:
            return
        # Lazy-loading attributes can contain the real image when src is a data placeholder.
        for field in ("data-src", "data-lazy-src", "src"):
            value = attrs.get(field)
            if value:
                url = urljoin(self.base_url, value.strip())
                if valid_url(url):
                    self.images.append(url)
                    break


def scrape_website(website):
    page_url = public_website(website.strip())
    parsed = urlsplit(page_url)
    robots_url = urlunsplit((parsed.scheme, parsed.netloc, "/robots.txt", "", ""))
    try:
        with httpx.Client(timeout=15, follow_redirects=False, headers={"User-Agent": USER_AGENT}) as client:
            status, _, text = read_document(client, robots_url, 256_000)
            if status != 404:
                if status in (401, 403):
                    raise SearchError(403, "scraping_disallowed", "The official website does not allow automated image collection.")
                if status != 200:
                    raise SearchError(502, "robots_unavailable", "Could not check the website's robots.txt — try again or clear the website field to use search only.")
                robots = RobotFileParser()
                robots.parse(text.splitlines())
                if not robots.can_fetch(USER_AGENT, page_url):
                    raise SearchError(403, "scraping_disallowed", "The website's robots.txt does not allow image collection from this page — choose an allowed page or clear the website field.")
                # Avoid violating a requested crawl delay or request-rate interval.
                # Rather than block this demo for a long wait, use search only instead.
                rate = robots.request_rate(USER_AGENT)
                if robots.crawl_delay(USER_AGENT) or (rate and rate.seconds > 0):
                    raise SearchError(422, "website_rate_restricted", "This website requests a crawl delay — clear the website field to use image search only.")
            status, content_type, html = read_document(client, page_url, 2_000_000)
            if status != 200:
                raise SearchError(502, "website_unavailable", "Could not read the official website page — try another page or clear the website field.")
            if not any(kind in content_type.lower() for kind in ("text/html", "application/xhtml+xml")):
                raise SearchError(422, "website_not_html", "Enter a website page URL rather than an image or document URL.")
    except httpx.TimeoutException:
        raise SearchError(504, "website_timeout", "The official website took too long to respond — try again or clear the website field.") from None
    except httpx.HTTPError:
        raise SearchError(502, "website_unavailable", "Could not connect to the official website — try again or clear the website field.") from None
    parser = PageImages(page_url)
    parser.feed(html)
    return [ImageCandidate(
        id="img_" + hashlib.sha256(url.encode()).hexdigest()[:16],
        url=url, thumbnail_url=url, source_domain=parsed.hostname.lower(), source_type="scrape",
        category="other", relevance=None, flagged=False, flag_reason=None, included=True,
    ) for url in parser.images]
