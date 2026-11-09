"""TIPA public procurement board; observed path identities and literal pagers."""
import re
from urllib.parse import urljoin, urlsplit

from src.scrapers._board import BoardScraper, NoticeLink, date_field
from src.scrapers._html import StructureError, parse_html
from src.core.normalizer import normalize_whitespace


class TipaBidScraper(BoardScraper):
    source = 'tipa_legacy_bid'

    def parse_list(self, response):
        table = parse_html(response).one('table', cls='basic_table center')
        if not all(s in table.one('thead').text() for s in ('제목', '작성일')):
            raise StructureError('changed TIPA list headings')
        result = {}
        for row in table.one('tbody').elements('tr'):
            links = [a for a in row.find('a') if re.fullmatch(r'/s040305/view/(?:page/[0-9]+/)?id/[0-9]+', a.attrs.get('href', ''))]
            if len(links) != 1:
                raise StructureError('missing TIPA notice identity')
            anchor = links[0]
            identity = anchor.attrs['href'].rsplit('/', 1)[1]
            cells = row.elements('td')
            if len(cells) != 5:
                raise StructureError('changed TIPA list cells')
            # The anchor title omits the nested "N" new-notice badge.
            title = normalize_whitespace(anchor.attrs.get('title') or anchor.text())
            result.setdefault(identity, NoticeLink(identity, title,
                urljoin(self.config['list_url'], '/s040305/view/id/' + identity), date_field(cells[4].text())))
        if not result:
            raise StructureError('unverified empty TIPA list')
        return list(result.values())

    def page_links(self, html):
        origin = urlsplit(self.config['list_url'])
        pages = {}
        for a in parse_html(html).find('a'):
            if not a.text().isdecimal():
                continue
            target = urlsplit(urljoin(self.config['list_url'], a.attrs.get('href', '')))
            match = re.fullmatch(r'/s040305/index/page/([0-9]+)', target.path)
            if match and target.netloc == origin.netloc and target.scheme == origin.scheme and not target.query:
                pages[int(match[1])] = target.geturl()
        return [pages[p] for p in sorted(pages)]

    def fetch_list(self):
        # Reuse the shared bounded collection and incremental hooks, with the
        # site's observed path pager instead of the query-only BoardScraper pager.
        pages, pending, visited = [], [self.config['list_url']], set()
        while pending and self.may_fetch_list_page(len(pages)):
            url = pending.pop(0)
            if url in visited:
                continue
            visited.add(url)
            html = self.request_text(url)
            pages.append(html)
            if self.list_page_complete(self.parse_list(html)):
                break
            pending.extend(u for u in self.page_links(html) if u not in visited and u not in pending)
        return pages

    def parse_detail(self, response, item):
        root = parse_html(response)
        return self.detail(item, root.one('td', cls='post-title'), root.one('div', cls='bbs-html'))
