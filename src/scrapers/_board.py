"""Shared fixture-backed board behavior; selectors live in site adapters."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from urllib.parse import parse_qs, urljoin, urlsplit

from src.core.models import Notice
from src.core.normalizer import (
    clean_content_text, generate_content_hash, generate_notice_id,
    normalize_date, normalize_institution, normalize_url, normalize_whitespace,
)
from src.scrapers.base import BaseScraper
from src.scrapers._html import Node, StructureError, parse_html


@dataclass(frozen=True)
class NoticeLink:
    source_notice_id: str
    title: str
    url: str
    published_at: str | None = None
    apply_start: str | None = None
    apply_end: str | None = None
    institution: str | None = None
    category: str | None = None


@dataclass(frozen=True)
class ParsedNotice:
    link: NoticeLink
    content_text: str


def date_field(text: str | None) -> str | None:
    if text is None or text.strip() in ('', '-'):
        return None
    # Observed metadata may include a time; do not infer partial dates in prose.
    match = re.fullmatch(r'\s*([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})(?:\s+[0-9]{1,2}:[0-9]{2})?\s*', text)
    value = normalize_date(match.group(1)) if match else None
    if value is None:
        raise StructureError('unrecognized date metadata')
    return value


def date_range(text: str | None):
    if text is None:
        return None, None
    match = re.match(r'^\s*([0-9]{4}-[0-9]{2}-[0-9]{2})\s*~\s*([0-9]{4}-[0-9]{2}-[0-9]{2})(?:\s|$)', text)
    if not match:
        raise StructureError('unrecognized application date range')
    return date_field(match[1]), date_field(match[2])


class BoardScraper(BaseScraper[NoticeLink, ParsedNotice]):
    source = ''
    id_parameter = ''
    detail_path = ''
    detail_query = {}

    def __init__(self, site_config, *, clock=None, **kwargs):
        super().__init__(site_config, **kwargs)
        if self.source_id != self.source:
            raise ValueError('wrong site config for scraper')
        self.clock = clock if clock is not None else lambda: datetime.now(timezone.utc)

    def build_detail_url(self, href: str) -> str:
        url = normalize_url(urljoin(self.config['list_url'], href))
        parts = urlsplit(url)
        if parts.netloc != urlsplit(self.config['list_url']).netloc or parts.path != self.detail_path:
            raise StructureError('unexpected detail URL origin/path')
        query = parse_qs(parts.query)
        if any(query.get(key) != [value] for key, value in self.detail_query.items()):
            raise StructureError('unexpected detail board/action')
        ids = query.get(self.id_parameter, [])
        if len(ids) != 1 or not re.fullmatch(r'[0-9]+', ids[0]):
            raise StructureError('missing/invalid detail identity')
        return url

    def link(self, anchor: Node, **fields) -> NoticeLink:
        url = self.build_detail_url(anchor.attrs.get('href', ''))
        title = normalize_whitespace(anchor.attrs.get('title') or anchor.text())
        if not title:
            raise StructureError('missing notice title')
        return NoticeLink(parse_qs(urlsplit(url).query)[self.id_parameter][0], title, url, **fields)

    def fetch_detail(self, item):
        return self.request_text(item.url)

    def detail(self, item, title_node, body, *, published=None, start=None, end=None, institution=None):
        title = title_node.text()
        content = body.text()
        if not title or not content:
            raise StructureError('empty detail title/body')
        if normalize_whitespace(title) != normalize_whitespace(item.title):
            raise StructureError('list/detail title mismatch; refetch the list before retrying')
        return ParsedNotice(replace(
            item, title=title, published_at=date_field(published) if published is not None else item.published_at,
            apply_start=start if start is not None else item.apply_start,
            apply_end=end if end is not None else item.apply_end,
            institution=institution or item.institution,
        ), content)

    def normalize(self, parsed):
        item = parsed.link
        now = self.clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError('observation clock must be timezone-aware')
        stamp = now.isoformat()
        content = clean_content_text(parsed.content_text)
        return Notice(
            notice_id=generate_notice_id(source_id=self.source_id, title=item.title, url=item.url, source_notice_id=item.source_notice_id),
            source_id=self.source_id, institution=normalize_institution(item.institution or self.config['institution']),
            title=normalize_whitespace(item.title), category=item.category,
            published_at=item.published_at, apply_start=item.apply_start, apply_end=item.apply_end,
            url=normalize_url(item.url), content_text=content, content_hash=generate_content_hash(content_text=content),
            first_seen_at=stamp, last_seen_at=stamp, updated_at=stamp,
        )


class TableBoardScraper(BoardScraper):
    table_class = ''
    title_cell_class = None
    date_index = None
    headers = ()

    def list_table(self, root):
        return root.one('table', cls=self.table_class)

    def parse_list(self, response):
        table = self.list_table(parse_html(response))
        head = table.one('thead').text()
        if not all(label in head for label in self.headers):
            raise StructureError('changed list headings')
        rows = table.one('tbody').elements('tr')
        result = []
        seen = set()
        for row in rows:
            scope = row.one('td', cls=self.title_cell_class) if self.title_cell_class else row
            anchors = [a for a in scope.find('a') if self.id_parameter in parse_qs(urlsplit(a.attrs.get('href', '')).query)]
            if len(anchors) != 1:
                raise StructureError('expected one notice link per row')
            cells = row.elements('td')
            if self.date_index is not None and len(cells) <= self.date_index:
                raise StructureError('missing list date cell')
            fields = self.list_fields(row, cells)
            item = self.link(anchors[0], **fields)
            if item.source_notice_id not in seen:
                result.append(item)
                seen.add(item.source_notice_id)
        return result

    def list_fields(self, row, cells):
        return {'published_at': date_field(cells[self.date_index].text())} if self.date_index is not None else {}
