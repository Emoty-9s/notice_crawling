"""Shared fixture-backed board behavior; selectors live in site adapters."""

from __future__ import annotations

import re
import base64
import hashlib
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
from src.scrapers.pagination import collection_pages


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
    body_html: str = ''


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
        self.max_pages = collection_pages(self.config)

    def page_links(self, html):
        """Follow literal numeric pager hrefs, never synthesize a URL.

        Parameter names come from audited config. Origin/path/board filters
        must match the canonical monitoring list. JS navigation fails closed.
        """
        from urllib.parse import parse_qsl
        pagination = self.config.get('pagination', {})
        parameter = pagination.get('parameter')
        if not parameter:
            return []
        origin = urlsplit(normalize_url(self.config['list_url']))
        expected = dict(parse_qsl(origin.query))
        links = []
        for anchor in parse_html(html).find('a'):
            if not anchor.text().strip().isdecimal():
                continue
            href = anchor.attrs.get('href', '')
            if not href or href.lower().startswith(('#', 'javascript:')):
                continue  # Active page has no navigation target.
            try:
                target = normalize_url(urljoin(self.config['list_url'], href))
            except ValueError:
                continue  # Unrelated numeric navigation is not a list pager.
            parts = urlsplit(target)
            query = parse_qs(parts.query)
            if (parts.scheme, parts.netloc, parts.path) != (origin.scheme, origin.netloc, origin.path):
                continue
            if parameter not in query:
                continue
            if len(query[parameter]) != 1 or not query[parameter][0].isdecimal():
                raise StructureError('INVALID_OBSERVED_PAGE')
            if any(query.get(k) != [v] for k, v in expected.items() if k != parameter):
                raise StructureError('UNEXPECTED_PAGINATION_BOARD')
            if target not in links:
                links.append(target)
        return sorted(links, key=lambda u: int(parse_qs(urlsplit(u).query)[parameter][0]))

    def fetch_list(self):
        first = self.config['list_url']
        pages = [self.request_text(first)]
        parameter = self.config.get('pagination', {}).get('parameter')
        visited = {int(parse_qs(urlsplit(first).query).get(parameter, ['0' if parameter == 'pager.offset' else '1'])[0])}
        pending = []
        for html in pages:
            items = self.parse_list(html)  # Unknown structure fails inside this source.
            if self.list_page_complete(items):
                return pages
            for target in self.page_links(html):
                page = int(parse_qs(urlsplit(target).query)[parameter][0])
                if page not in visited and all(p != page for p,_ in pending):
                    pending.append((page,target))
            if pending:
                if not self.may_fetch_list_page(len(pages)):
                    return pages
                page,target = pending.pop(0)
                pages.append(self.request_text(target))
                visited.add(page)
        return pages

    def _parse_items(self, response):
        if not isinstance(response, list):
            return super()._parse_items(response)
        records = {}
        for html in response:
            for item in self.parse_list(html):
                # Pinned notices recur on later pages; preserve first/newest.
                records.setdefault(item.source_notice_id, item)
        return list(records.values())

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

    def detail(self, item, title_node, body, *, published=None, start=None, end=None, institution=None,
               allow_image_body=False):
        title = title_node.text()
        content = body.text()
        if not content:
            # Some real notices contain only a poster. Preserve the observed
            # resource identity for hashing; never invent OCR/body prose.
            images = []
            for image in body.find('img'):
                src = image.attrs.get('src', '').strip()
                if not src:
                    continue
                embedded = re.fullmatch(r'data:image/(png|jpeg|gif|webp);base64,([A-Za-z0-9+/=\s]+)', src)
                if embedded:
                    try:
                        data = base64.b64decode(''.join(embedded[2].split()), validate=True)
                    except ValueError:
                        continue
                    if data:
                        images.append('embedded-image-sha256:' + hashlib.sha256(data).hexdigest())
                    continue
                try:
                    url = normalize_url(urljoin(item.url, src))
                except ValueError:
                    continue
                if url not in images:
                    images.append(url)
            if images:
                content = '[이미지 본문: 텍스트 미추출, OCR 미수행] ' + ' '.join(images)
        if not content and self.extractor is not None:
            # Attachment-only notices still reach the common extraction stage.
            content = '[추출 미완료: 원문 확인 필요]'
        if not title or not content:
            raise StructureError('empty detail title/body')
        if normalize_whitespace(title) != normalize_whitespace(item.title):
            raise StructureError('list/detail title mismatch; refetch the list before retrying')
        return ParsedNotice(replace(
            item, title=title, published_at=date_field(published) if published is not None else item.published_at,
            apply_start=start if start is not None else item.apply_start,
            apply_end=end if end is not None else item.apply_end,
            institution=institution or item.institution,
        ), content, body.html())

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

    def notice_id_for(self, item):
        return generate_notice_id(source_id=self.source_id,title=item.title,url=item.url,
                                  source_notice_id=item.source_notice_id)


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
