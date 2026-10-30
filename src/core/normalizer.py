"""Pure, site-independent normalization and versioned stable identity (M03).

No network, clock, persistence, status transitions or Gemini calls. Identity
rules are versioned: changing them later requires an explicit data migration.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit


def normalize_whitespace(text: str) -> str:
    """NFC Unicode and collapse all Unicode whitespace to a single space."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return " ".join(unicodedata.normalize("NFC", text).split())


def normalize_institution(institution: str) -> str:
    """Normalize presentation only; retain legal prefixes and distinct names."""
    return normalize_whitespace(institution)


def normalize_date(value: str | None) -> str | None:
    """Return YYYY-MM-DD for a complete supported date, else None.

    Supports YYYY-MM-DD, YYYY.MM.DD, YYYY/MM/DD and Korean year/month/day,
    optionally followed by a Korean weekday in parentheses. Does not infer
    missing years, extract a date from prose/ranges or truncate timestamps.
    """
    if value is None:
        return None
    text = normalize_whitespace(value)
    text = re.sub(r"\s*\([월화수목금토일](?:요일)?\)$", "", text).strip()
    match = re.fullmatch(
        r"([0-9]{4})\s*([./-])\s*([0-9]{1,2})\s*\2\s*([0-9]{1,2})\.?",
        text,
    )
    if match:
        year, month, day = match.group(1, 3, 4)
    else:
        match = re.fullmatch(r"([0-9]{4})\s*년\s*([0-9]{1,2})\s*월\s*([0-9]{1,2})\s*일", text)
        if not match:
            return None
        year, month, day = match.groups()
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def normalize_url(url: str) -> str:
    """Canonicalize an absolute HTTP(S) URL without changing query semantics.

    Strip surrounding whitespace and fragment; lowercase scheme/host, remove
    default ports and use '/' for an empty root path. Preserve path case,
    non-root trailing slashes, encoding, query ordering/duplicates and values.
    Empty input stays empty for ID fallback. Relative/invalid URLs are errors;
    callers must resolve relative links before normalization.
    """
    if not isinstance(url, str):
        raise TypeError("url must be a string")
    text = url.strip()
    if not text:
        return ""
    if any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in text):
        raise ValueError("URL must not contain unescaped whitespace/control characters")
    parts = urlsplit(text)
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("URL must be an absolute HTTP(S) URL")
    if parts.username is not None or parts.password is not None:
        raise ValueError("URL must not contain credentials")
    host = parts.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    port = parts.port  # also validates malformed/out-of-range ports
    if port is not None and (scheme, port) not in (("http", 80), ("https", 443)):
        host = f"{host}:{port}"
    return urlunsplit((scheme, host, parts.path or "/", parts.query, ""))


def clean_content_text(content_text: str) -> str:
    """Clean already-extracted plain text; retain punctuation, case and numbers.

    Does not treat literal '<' or '&' as HTML, or guess which prose is menu
    text. Use html_to_content_text explicitly when the input is HTML.
    """
    return normalize_whitespace(content_text)


class _BodyTextParser(HTMLParser):
    """Generic structural cleanup; site-specific body selection is a scraper job."""

    _excluded = {"head", "script", "style", "nav", "header", "footer", "template"}
    _separators = {
        "address", "article", "aside", "blockquote", "br", "dd", "div", "dl",
        "dt", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "li", "ol", "p",
        "pre", "section", "table", "td", "th", "tr", "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.excluded_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self._excluded:
            self.excluded_stack.append(tag)
        if tag in self._separators or tag in self._excluded:
            self.parts.append(" ")

    def handle_startendtag(self, tag: str, attrs: list) -> None:
        # Self-closing excluded elements must not suppress following text.
        if tag in self._separators or tag in self._excluded:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.excluded_stack:
            # Recover from a missing inner closing tag inside an excluded block.
            index = len(self.excluded_stack) - 1 - self.excluded_stack[::-1].index(tag)
            del self.excluded_stack[index:]
        if tag in self._separators or tag in self._excluded:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self.excluded_stack:
            self.parts.append(data)


def html_to_content_text(html: str) -> str:
    """Extract text, decode entities and drop generic non-body HTML elements.

    No fetching, DOM selectors, attachment parsing or JavaScript execution.
    HTMLParser is tolerant, not a browser: malformed markup can still require
    a scraper to select/repair the actual content fragment.
    """
    if not isinstance(html, str):
        raise TypeError("html must be a string")
    parser = _BodyTextParser()
    parser.feed(html)
    parser.close()
    return clean_content_text("".join(parser.parts))


def _optional_identifier(value: str | None) -> str | None:
    if value is None:
        return None
    return normalize_whitespace(value) or None


def generate_notice_id(
    *, source_id: str, title: str, url: str,
    source_notice_id: str | None = None, notice_number: str | None = None,
    url_is_stable: bool = True,
) -> str:
    """Implement models.NoticeIdGenerator with a source-scoped SHA-256 ID.

    Priority: site ID > notice number > stable URL > title/canonical URL hash.
    By default a supplied URL is a stable detail URL, as required by the Notice
    contract. Set url_is_stable=False for a known non-unique/unstable URL; no
    site-specific URL guessing occurs. Supply a stable ID when possible: a
    fallback ID can change when its title/URL changes. Never pass session URLs.
    """
    source = normalize_whitespace(source_id)
    if not source:
        raise ValueError("source_id must not be empty")
    if type(url_is_stable) is not bool:
        raise TypeError("url_is_stable must be a boolean")
    site_id = _optional_identifier(source_notice_id)
    number = _optional_identifier(notice_number)
    if site_id is not None:
        kind, identity = "site-id", site_id
    elif number is not None:
        kind, identity = "notice-number", number
    else:
        canonical_url = normalize_url(url)
        if canonical_url and url_is_stable:
            kind, identity = "detail-url", canonical_url
        else:
            normalized_title = normalize_whitespace(title)
            if not normalized_title:
                raise ValueError("fallback identity requires a nonempty title")
            kind, identity = "title-url", [normalized_title, canonical_url]
    payload = json.dumps(
        ["notice-id-v1", source, kind, identity],
        ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")
    return "notice:v1:" + hashlib.sha256(payload).hexdigest()


def generate_content_hash(*, content_text: str) -> str:
    """Implement models.ContentHashGenerator for normalized plain text only.

    Whitespace/NFC-equivalent bodies share a hash. Meaningful punctuation,
    amounts, dates and wording remain significant. Metadata is not included.
    Empty bodies get the deterministic empty-text hash, not a missing value.
    """
    normalized = clean_content_text(content_text)
    return "content:v1:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()
