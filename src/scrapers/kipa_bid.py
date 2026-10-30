"""KIPA public tenders; attachment names are excluded from the body."""

from src.scrapers._board import TableBoardScraper
from src.scrapers._html import field_value, parse_html


class KipaBidScraper(TableBoardScraper):
    source = 'kipa_bid'
    id_parameter = 'article_no'
    detail_path = '/kipa/notice/kw_0402.jsp'
    detail_query = {'mode': 'view', 'board_no': '15'}
    table_class = 'list_table'
    date_index = 2
    headers = ('제목', '등록일')

    def parse_detail(self, response, item):
        table = parse_html(response).one('table', cls='view_table')
        return self.detail(item, table.one('td', cls='title'), table.one('div', id='article_text'),
                           published=field_value(table, '등록일'))
