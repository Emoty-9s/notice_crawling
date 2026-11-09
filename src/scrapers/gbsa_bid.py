"""GBSA public procurement and its observed eGov file links."""
import re
from urllib.parse import urljoin
from src.scrapers._board import TableBoardScraper
from src.scrapers._html import StructureError, field_value, parse_html


class GbsaBidScraper(TableBoardScraper):
    source = 'gbsa_bid'
    id_parameter = 'nttId'
    detail_path = '/board/bid_info.do'
    table_class = 'tbl-basic bbs-list'
    date_index = 3
    headers = ('번호', '등록일')

    def page_links(self, response):
        pages = {}
        for a in parse_html(response).find('a'):
            match = re.fullmatch(r'fn_egov_select_noticeList\(([1-9][0-9]*)\);\s*return false;', a.attrs.get('onclick', ''))
            if match and a.text().isdecimal() and int(a.text()) == int(match[1]):
                pages[int(match[1])] = self.config['list_url']+'?pageIndex='+match[1]
        return [pages[p] for p in sorted(pages)]

    def parse_detail(self, response, item):
        table = parse_html(response).one('table', cls='bbs-view')
        return self.detail(item, table.one('td', cls='bio-name'), table.one('div', id='bbs_cn'),
                           published=field_value(table, '등록일'))

    def parse_attachments(self, response):
        result = []
        for a in parse_html(response).one('table', cls='bbs-view').find('a'):
            href = a.attrs.get('href', '')
            if 'fn_egov_downFile' not in href:
                continue
            match = re.fullmatch(r"javascript:fn_egov_downFile\('(FILE_[0-9]+)','([0-9]+)'\)", href)
            if not match:
                raise StructureError('changed GBSA attachment identity')
            result.append(urljoin(self.config['list_url'], '/cmm/fms/FileDown.do?atchFileId='+match[1]+'&fileSn='+match[2]))
        return list(dict.fromkeys(result))
