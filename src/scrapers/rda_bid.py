"""RDA tender table and dedicated #contents body from the saved DOM."""

import re
import hashlib
from urllib.parse import urlencode, urljoin

from src.scrapers._board import TableBoardScraper, date_field
from src.scrapers._html import StructureError, field_value, parse_html


class RdaBidScraper(TableBoardScraper):
    source = 'rda_bid'
    id_parameter = 'dataNo'
    detail_path = '/board/board.do'
    detail_query = {'mode': 'updateCnt', 'boardId': 'bidancm', 'prgId': 'bid_bidancmEntry'}
    table_class = 'tbl data'
    headers = ('제목', '기관명', '종료일')

    def list_table(self, root):
        # An address-search modal also has table.tbl.data; use the observed caption.
        tables = [t for t in root.find('table', cls=self.table_class)
                  if any('입찰공고 안내' in c.text() for c in t.find('caption'))]
        if len(tables) != 1:
            raise StructureError('missing/ambiguous tender list table')
        return tables[0]

    def list_fields(self, row, cells):
        return {
            'institution': row.one('td', attr={'aria-label': '기관명'}).text(),
            'category': row.one('td', attr={'aria-label': '분야'}).text() or None,
            'apply_end': date_field(row.one('td', attr={'aria-label': '종료일'}).text()),
        }

    def parse_detail(self, response, item):
        root = parse_html(response)
        title = root.one('div', cls='community-page-title', id='title')
        return self.detail(item, title.one('h2', cls='tit'), root.one('div', cls='g-description-area', id='contents'),
                           published=field_value(title, '작성일'), institution=field_value(title, '기관명'),
                           end=date_field(title.one('span', cls='category').text()))

    def parse_attachments(self, response):
        root = parse_html(response)
        scopes = root.find(id='attach-file')
        if not scopes:
            return tuple(r.url for r in self._literal_attachments(response))
        calls = [n.attrs['onclick'] for n in scopes[0].find() if 'fn_download(' in n.attrs.get('onclick','')]
        resolved = {'unresolved:'+hashlib.sha256(c.strip().encode()).hexdigest() for c in calls}
        links = [r.url for r in self._literal_attachments(scopes[0].html()) if r.url not in resolved]
        if calls and '"/fileDownLoadDw.do?boardId="+boardId+"&dataNo="+dataNo+"&sortNo="+sortNo' not in response:
            raise StructureError('UNVERIFIED_RDA_DOWNLOAD_HANDLER')
        for call in calls:
            match = re.fullmatch(r"\s*fn_download\('([A-Za-z0-9_]+)','([0-9]+)','([0-9]+)'\);?\s*",call)
            if match is None or match[1] != 'bidancm':
                raise StructureError('UNVERIFIED_RDA_ATTACHMENT')
            query = urlencode(dict(boardId=match[1],dataNo=match[2],sortNo=match[3]))
            links.append(urljoin(self.config['list_url'],'/fileDownLoadDw.do?'+query))
        return tuple(dict.fromkeys(links))

    def _literal_attachments(self, html):
        from src.core.extraction import discover
        return [r for r in discover(html,self.config['list_url']) if r.kind != 'image']
