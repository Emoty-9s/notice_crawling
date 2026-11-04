"""M16 semantic-table parsing, shared robots/paging and source-specific hooks.

Site adapters interpret only the literal JS/form contracts in saved HTML.
Live HTTP/XHR verification is still required before claiming operational success.
"""

import re
from dataclasses import replace
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from src.core.normalizer import generate_notice_id, normalize_date, normalize_url, normalize_whitespace
from ._board import BoardScraper, NoticeLink, ParsedNotice
from ._html import StructureError, parse_html


def period(text, *, year=None):
    """Use a complete date or an explicit source business year, never the clock."""
    if text is None or normalize_whitespace(text) in ('', '-'):
        return None, None
    dates = re.findall(r'(?<![0-9])([0-9]{4}[./-][0-9]{1,2}[./-][0-9]{1,2})(?![0-9])', text)
    if not dates and year is not None and re.fullmatch(r'[0-9]{4}', str(year)):
        partial = re.findall(r'(?<![0-9.])([0-9]{1,2})[./]([0-9]{1,2})(?![0-9.])', text)
        dates = [f'{year}-{month}-{day}' for month, day in partial]
    if len(dates) != 2 or '~' not in text:
        raise StructureError('UNVERIFIED_APPLICATION_PERIOD: two complete dates required')
    values = tuple(normalize_date(value) for value in dates)
    if any(value is None for value in values) or values[0] > values[1]:
        raise StructureError('INVALID_APPLICATION_PERIOD')
    return values


def label(text):
    return re.sub(r'\s+', '', text).rstrip(':：')


def public_url(url):
    """Remove servlet URL session credentials without changing resource identity."""
    return re.sub(r';jsessionid=[^/?#;\s\"\']+', '', url, flags=re.I)


def metadata(root, name):
    """Existing field_value contract, with source label spacing normalized."""
    values = []
    for node in root.find():
        if node.tag in ('th', 'dt') and label(node.text()) == label(name):
            if root.tag == 'table':
                parent = node.parent
                while parent is not None and parent.tag != 'table':
                    parent = parent.parent
                if parent is not root:
                    continue
            siblings = node.parent.elements()
            index = siblings.index(node)
            if index + 1 < len(siblings) and siblings[index + 1].tag in ('td', 'dd'):
                values.append(siblings[index + 1])
    if len(values) > 1:
        raise StructureError('AMBIGUOUS_DETAIL_METADATA')
    return values[0] if values else None


class PortalScraper(BoardScraper):
    """Uses BaseScraper's transport/timeout/retry/UA and source failure boundary.

    Bounded newest-page window: default 3 pages, configurable 1..20. Every page
    and detail must be allowed by robots. Unknown JS is not empty data.
    """

    headers = ()
    identity_parameters = ()
    category_label = ''
    body_label = '공고 내용'
    detail_period_label = '접수기간'

    def __init__(self, site_config, **kwargs):
        super().__init__(site_config, **kwargs)
        self._robots = None
        parts = urlsplit(normalize_url(self.config['list_url']))
        self.origin = (parts.scheme, parts.netloc)
        self.list_path = parts.path.replace('//', '/')

    def fetch_list(self):
        robots_url = urlunsplit((*self.origin, '/robots.txt', '', ''))
        self._robots = RobotFileParser(robots_url)
        try:
            robots_text = self.request_text(robots_url)
        except HTTPError as error:
            if error.code != 404:
                raise
            robots_text = ''  # Standard absent robots file; never ignore 403/5xx.
        if '<html' in robots_text.lower() or '<!doctype' in robots_text.lower():
            raise StructureError('UNVERIFIED_ROBOTS_RESPONSE')
        self._robots.parse(robots_text.splitlines())
        first = self._allowed(self.config['list_url'])
        first_html = self.request_text(first)
        return self._fetch_pages(first, first_html)

    def _fetch_pages(self, first, first_html):
        pages, queue, visited = [first_html], [(first, first_html)], {first}
        # Keep pages as separate documents; never concatenate DOMs/duplicate IDs.
        for current, html in queue:
            self.parse_list(html)  # Fail before traversing an unknown shell.
            links = self.page_links(html)
            for target in links:
                if target in visited:
                    continue
                if len(pages) >= self.max_pages:
                    self.logger.warning('pagination_window_capped source_id=%s max_pages=%d', self.source_id, self.max_pages)
                    return pages
                visited.add(target)
                response = self.request_text(self._allowed(target))
                pages.append(response)
                queue.append((target, response))
        return pages

    def _allowed(self, url):
        canonical = normalize_url(url)
        parts = urlsplit(canonical)
        if (parts.scheme, parts.netloc) != self.origin:
            raise StructureError('UNEXPECTED_REQUEST_ORIGIN')
        if self._robots is not None and not self._robots.can_fetch(self.http_settings.user_agent, canonical):
            raise StructureError('ROBOTS_DISALLOWED')
        return canonical

    def build_detail_url(self, href):
        url = normalize_url(urljoin(self.config['list_url'], public_url(href)))
        parts = urlsplit(url)
        if (parts.scheme, parts.netloc) != self.origin or parts.path.replace('//', '/') != self.detail_path:
            raise StructureError('UNEXPECTED_DETAIL_URL')
        query = parse_qs(parts.query)
        if any(len(query.get(key, [])) != 1 or not re.fullmatch(r'[0-9]+', query[key][0]) for key in self.identity_parameters):
            raise StructureError('MISSING_DETAIL_IDENTITY')
        if any(query.get(key) != [value] for key, value in self.detail_query.items()):
            raise StructureError('UNEXPECTED_DETAIL_BOARD')
        # Stable public URL includes the natural year+sequence pair. Discard
        # navigation/search/session parameters rather than persist session URLs.
        pairs = [(key, query[key][0]) for key in self.identity_parameters]
        pairs += list(self.detail_query.items())
        return urlunsplit((*self.origin, self.detail_path, urlencode(pairs), ''))

    def _table(self, root):
        tables = []
        for table in root.find('table'):
            heads = [label(node.text()) for node in table.find('th')]
            if all(label(name) in heads for name in self.headers):
                tables.append(table)
        if len(tables) != 1:
            raise StructureError('UNVERIFIED_LIST_TABLE')
        return tables[0]

    def parse_list(self, response):
        if isinstance(response, list):
            merged = {}
            for page in response:
                for item in self.parse_list(page):
                    if item.url in merged and merged[item.url] != item:
                        raise StructureError('CONFLICTING_DUPLICATE_NOTICE')
                    merged[item.url] = item
            return list(merged.values())
        root = parse_html(response)
        table = self._table(root)
        result, seen = [], {}
        rows = table.find('tr')
        for row in rows:
            cells = row.elements('td')
            if not cells:
                continue
            if len(cells) == 1 and cells[0].attrs.get('colspan'):
                if cells[0].text() in ('검색 결과가 없습니다.', '등록된 공고가 없습니다.', 'There is no data. please choose another seach keyword'):
                    continue
                raise StructureError('UNVERIFIED_EMPTY_LIST')
            if len(cells) != len(self.headers):
                raise StructureError('CHANGED_LIST_COLUMNS')
            fields = {name: cell for name, cell in zip(self.headers, cells)}
            title_cell = fields[self.title_label]
            anchors = [anchor for anchor in title_cell.find('a') if self.detail_path in anchor.attrs.get('href', '').replace('//', '/')]
            if len(anchors) != 1:
                raise StructureError('UNVERIFIED_DETAIL_LINK: raw DOM or XHR capture required')
            url = self.build_detail_url(anchors[0].attrs['href'])
            title = normalize_whitespace(anchors[0].text())
            if not title:
                raise StructureError('MISSING_NOTICE_TITLE')
            source_year = parse_qs(urlsplit(url).query).get('bizYear', [None])[0]
            start, end = period(fields[self.period_label].text(), year=source_year)
            category = normalize_whitespace(fields[self.category_label].text())
            institution = fields['센터'].text() if '센터' in fields else self.config['institution']
            item = NoticeLink(url, title, url, apply_start=start, apply_end=end,
                              category=category if category not in ('', '-') else None,
                              institution=institution if institution not in ('', '-') else None)
            if url in seen and seen[url] != item:
                raise StructureError('CONFLICTING_DUPLICATE_NOTICE')
            if url not in seen:
                result.append(item)
                seen[url] = item
        # A bare tbody on RIPC is the observed JS shell, not a proven empty list.
        if not result and not any(row.elements('td') for row in rows):
            raise StructureError('UNVERIFIED_DYNAMIC_LIST: data endpoint not confirmed')
        return result

    def page_links(self, html):
        root = parse_html(html)
        table = self._table(root)
        links = []
        for anchor in root.find('a'):
            parent = anchor.parent
            in_table = False
            while parent is not None:
                if parent is table:
                    in_table = True
                    break
                parent = parent.parent
            text = anchor.text().strip()
            if in_table or not (text.isdecimal() or text in ('다음', '다음페이지', 'Next', 'next', '>')):
                continue
            href = anchor.attrs.get('href', '')
            if not href or href.startswith(('#', 'javascript:')):
                raise StructureError('UNVERIFIED_JAVASCRIPT_PAGINATION')
            url = normalize_url(urljoin(self.config['list_url'], public_url(href)))
            parts = urlsplit(url)
            query = parse_qs(parts.query)
            if ((parts.scheme, parts.netloc) != self.origin or parts.path.replace('//', '/') != self.list_path
                    or any(query.get(key) != [value] for key, value in self.detail_query.items())):
                raise StructureError('UNEXPECTED_PAGINATION_TARGET')
            if url not in links:
                links.append(url)
        return links

    def fetch_detail(self, item):
        return self.request_text(self._allowed(item.url))

    def parse_attachments(self, response):
        root = parse_html(response)
        scope = metadata(root, '첨부파일')
        if scope is None:
            return ()
        links = []
        for anchor in scope.find('a'):
            href = anchor.attrs.get('href', '')
            if not href or href.startswith(('#', 'javascript:')):
                raise StructureError('UNVERIFIED_ATTACHMENT_LINK')
            url = normalize_url(urljoin(self.config['list_url'], public_url(href)))
            if url not in links:
                links.append(url)
        return tuple(links)

    def parse_detail(self, response, item):
        root = self.detail_scope(response)
        title_node = metadata(root, '공고명')
        if title_node is None or normalize_whitespace(title_node.text()) != normalize_whitespace(item.title):
            raise StructureError('DETAIL_TITLE_MISMATCH')
        dates = metadata(root, self.detail_period_label)
        business_year = metadata(root, '사업년도')
        year_text = business_year.text().removesuffix('년').strip() if business_year is not None else None
        start, end = period(dates.text(), year=year_text) if dates is not None else (item.apply_start, item.apply_end)
        category_node = metadata(root, self.detail_category_label)
        category = normalize_whitespace(category_node.text()) if category_node is not None else item.category
        if category in ('', '-'):
            category = None
        # No readable body is allowed by Notice. Do not synthesize eligibility
        # or turn attachment labels/navigation into the notice body.
        content = self.detail_content(root)
        self.parse_attachments(response)  # Validate exposed links, never download.
        return ParsedNotice(replace(item, apply_start=start, apply_end=end,
                                    category=category or None), content)

    def detail_scope(self, response):
        return parse_html(response)

    def detail_content(self, root):
        body = metadata(root, self.body_label)
        return body.text() if body is not None else ''

    def normalize(self, parsed):
        # Complete year+sequence identity is the canonical detail URL. M03's
        # existing stable-URL branch avoids collisions of yearly annId values.
        original = super().normalize(parsed)
        return replace(original, notice_id=generate_notice_id(source_id=self.source_id,
                       title=original.title, url=original.url))
