"""KHIDI selectors verified against the supplied list/detail HTML."""

from src.scrapers._board import TableBoardScraper
from src.scrapers._html import StructureError, field_value, parse_html


class KhidiBusinessScraper(TableBoardScraper):
    source = 'khidi_business'
    id_parameter = 'linkId'
    detail_path = '/board/view'
    detail_query = {'menuId': 'MENU01108'}
    table_class = 'tstyle_list'
    title_cell_class = 'ellipsis'
    date_index = 3
    headers = ('제목', '등록일')

    def parse_detail(self, response, item):
        root = parse_html(response)
        if root.one('input', id='linkId').attrs.get('value') != item.source_notice_id:
            raise StructureError('detail identity mismatch')
        scope = root.one('article', cls='news_view')
        return self.detail(item, scope.one('h1', cls='newsTitle'), scope.one('div', cls='viewContent'),
                           published=field_value(scope.one('table', cls='tstyle_view'), '작성일'))
