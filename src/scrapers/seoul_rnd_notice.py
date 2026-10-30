"""Seoul R&D table and smartOutput body, excluding file and neighbour rows."""

from src.scrapers._board import TableBoardScraper
from src.scrapers._html import StructureError, field_value, parse_html


class SeoulRndNoticeScraper(TableBoardScraper):
    source = 'seoul_rnd_notice'
    id_parameter = 'seqNo'
    detail_path = '/client/c030200/c030200_04.jsp'
    table_class = 'tabW100'
    title_cell_class = 't1'
    date_index = 2
    headers = ('제목', '등록일')

    def list_table(self, root):
        return root.one('div', cls='board_list').one('table', cls=self.table_class)

    def parse_detail(self, response, item):
        scope = parse_html(response).one('div', cls='board_view')
        if scope.one('input', attr={'name': 'seqNo'}).attrs.get('value') != item.source_notice_id:
            raise StructureError('detail identity mismatch')
        return self.detail(item, scope.one('td', cls='tit'), scope.one('td', cls='view smartOutput'),
                           published=field_value(scope, '등록일'))
