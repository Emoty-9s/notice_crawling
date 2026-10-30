"""RDA tender table and dedicated #contents body from the saved DOM."""

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
