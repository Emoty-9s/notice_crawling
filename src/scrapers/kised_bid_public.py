"""KISED public tender board; list rows are ul, not table/tr."""

from src.scrapers._board import BoardScraper, date_range
from src.scrapers._html import StructureError, field_value, parse_html


class KisedBidPublicScraper(BoardScraper):
    source = 'kised_bid_public'
    id_parameter = 'list_no'
    detail_path = '/board.es'
    detail_query = {'act': 'view', 'bid': '0005', 'mid': 'a10303000000'}

    def parse_list(self, response):
        scope = parse_html(response).one('div', cls='tstyle_list', id='panel_2')
        if not all(word in scope.one('div', cls='dhead').text() for word in ('공고명', '접수기간')):
            raise StructureError('changed tender list headings')
        result = []
        for row in scope.one('div', id='listView').elements('ul'):
            start, end = date_range(row.one('li', cls='W13').text())
            result.append(self.link(row.one('li', cls='title').one('a'), apply_start=start, apply_end=end))
        return result

    def parse_detail(self, response, item):
        root = parse_html(response)
        if root.one('input', attr={'name': 'list_no'}).attrs.get('value') != item.source_notice_id:
            raise StructureError('detail identity mismatch')
        table = root.one('table', cls='tbl-basic tbl-row')
        bodies = [td for td in table.find('td', cls='left') if td.attrs.get('colspan') == '4']
        if len(bodies) != 1:
            raise StructureError('missing/ambiguous detail body')
        start, end = date_range(field_value(table, '접수기간'))
        return self.detail(item, table.one('th', cls='board_tit'), bodies[0],
                           published=field_value(table, '최초작성일'), start=start, end=end)
