"""KIAT public procurement, including official application windows and files."""
import re
from html import unescape
from urllib.parse import parse_qs, urljoin, urlsplit

from src.scrapers._board import BoardScraper, NoticeLink, date_field
from src.scrapers._html import Node, StructureError, field_value, parse_html


def period(text):
    match = re.match(r'^\s*(\d{4}[-.]\d{2}[-.]\d{2})\([월화수목금토일]\)\s*~\s*(\d{4}[-.]\d{2}[-.]\d{2})\([월화수목금토일]\)', text)
    if not match:
        raise StructureError('changed KIAT application period')
    return date_field(match[1]), date_field(match[2])


class KiatBidScraper(BoardScraper):
    source = 'kiat_home'
    id_parameter = 'seq'
    detail_path = '/bidding/biddingView.do'

    def parse_list(self, response):
        table = parse_html(response).one('table', cls='announceListTable')
        if table.one('caption').text() != '공고현황 목록':
            raise StructureError('changed KIAT board')
        result = {}
        for row in table.one('tbody').elements('tr'):
            subject = row.one('p', cls='subject').one('a')
            url = self.build_detail_url(subject.attrs.get('href', ''))
            identity = parse_qs(urlsplit(url).query)['seq'][0]
            start, end = period(row.one('p', cls='period').text())
            # Receipt start is not a publication date. Keep unknown dates null.
            title = subject.text().removeprefix('<재공고>').strip()
            result.setdefault(identity, NoticeLink(identity, title,
                urljoin(self.config['list_url'], self.detail_path+'?seq='+identity),
                apply_start=start, apply_end=end, category=row.one('p', cls='service').text()))
        if not result:
            raise StructureError('unverified empty KIAT list')
        return list(result.values())

    def page_links(self, response):
        pages = {}
        for a in parse_html(response).one('div', cls='paging').find('a'):
            match = re.fullmatch(r'goPage\(([1-9][0-9]*)\);\s*return false;', a.attrs.get('onclick', ''))
            if match and a.text().isdecimal() and int(a.text()) == int(match[1]):
                pages[int(match[1])] = self.config['list_url']+'?page='+match[1]
        return [pages[p] for p in sorted(pages)]

    def parse_detail(self, response, item):
        root = parse_html(response)
        proem = root.one('div', cls='announceView_proem')
        subject = proem.one('p', cls='subject')
        title = Node('p', children=[c for c in subject.children
            if not isinstance(c, Node) or 'num' not in c.attrs.get('class', '').split()])
        # Keep only public detail tables; decode rich text stored in textarea.
        tables = root.one('div', id='container').find('table')
        if len(tables) != 5:
            raise StructureError('changed KIAT detail sections')
        start, end = period(field_value(tables[1], '접수기간') or '')
        body = Node('div', children=tables)
        for textarea in body.find('textarea'):
            textarea.children = parse_html(unescape(''.join(c for c in textarea.children if isinstance(c, str)))).children
            textarea.tag = 'div'
        return self.detail(item, title, body, start=start, end=end)

    def parse_attachments(self, response):
        result = []
        for a in parse_html(response).find('a', cls='btn_file'):
            match = re.fullmatch(r'javascript:doGuideDownload\(([0-9]+)\);', a.attrs.get('href', ''))
            if not match:
                raise StructureError('changed KIAT public attachment link')
            result.append(urljoin(self.config['list_url'], '/guideDownload/'+match[1]+'.do'))
        return list(dict.fromkeys(result))
