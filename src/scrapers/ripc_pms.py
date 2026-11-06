"""RIPC partner tender board, using the supplied HTML's explicit AJAX contract."""

import json
import re
from dataclasses import replace
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

from src.core.normalizer import html_to_content_text, normalize_whitespace
from ._board import NoticeLink
from ._html import StructureError, parse_html
from ._portal import PortalScraper, metadata, period, public_url


class RipcScraper(PortalScraper):
    source = 'ripc_pms'
    detail_path = '/pms/biz/partner/tenderNotice/info.do'
    identity_parameters = ('bizYear', 'noticeSeq')
    headers = ('공고번호', '센터', '사업형태', '공고제목', '공고기간', '배정예산', '공고상태')
    title_label = '공고제목'
    category_label = '사업형태'
    period_label = '공고기간'
    detail_category_label = '단위사업'
    detail_period_label = '공고기간'

    def ajax_request(self, html, page=1):
        """Only the action/fields/constants present in the saved doSearch JS."""
        self._table(parse_html(html))
        script = public_url(html)
        action = re.search(r'getNoticeList\s*:\s*\{\s*action\s*:\s*"([^"]+)"\s*,\s*method\s*:\s*"POST"', script)
        required = ('searchKeyword', 'bizYear', 'recordCountPerPage', 'currentPageNo',
                    'chkCenter', 'chkBizCategory', 'result.noticeList', 'result.totalRecordCount',
                    'result.recordCountPerPage', 'result.currentPageNo', '{{:noticeSeq}}', '{{:bizYear}}')
        if (action is None or action[1] != '/pms/biz/partner/tenderNotice/getNoticeList.do'
                or not all(value in script for value in required)
                or not re.search(r'"noticeGroupCode"\s*:\s*"NGR002"', script)
                or not re.search(r'"noticeCode"\s*:\s*"NST000"', script)):
            raise StructureError('CHANGED_RIPC_AJAX_CONTRACT')
        year = str(self.config.get('business_year', self.clock().year))
        if not re.fullmatch(r'[0-9]{4}', year):
            raise StructureError('INVALID_BUSINESS_YEAR')
        # jQuery omits empty checkbox arrays. No center/category filter selected.
        data = {'searchKeyword': '', 'bizYear': year, 'recordCountPerPage': '10',
                'currentPageNo': str(page), 'noticeGroupCode': 'NGR002', 'noticeCode': 'NST000'}
        return urljoin(self.config['list_url'], action[1]), data

    def _fetch_pages(self, first, first_html):
        if not parse_html(first_html).find('script', id='tmpl_noticeListRow'):
            return super()._fetch_pages(first, first_html)
        pages = []
        page = 0
        while True:
            page += 1
            endpoint, data = self.ajax_request(first_html, page)
            response = self.request_form(self._allowed(endpoint), data)
            result = self.json_result(response)
            if result['currentPageNo'] != page or result['recordCountPerPage'] != 10:
                raise StructureError('RIPC_PAGE_RESPONSE_MISMATCH')
            items = self.parse_list(response)
            pages.append(response)
            if self.list_page_complete(items):
                break
            if page * 10 >= result['totalRecordCount']:
                break
            if not result['noticeList']:
                raise StructureError('RIPC_MISSING_PAGE_ROWS')
            if not self.may_fetch_list_page(len(pages)):
                self.logger.warning('pagination_window_capped source_id=%s max_pages=%d', self.source_id, self.max_pages)
                break
        return pages

    @staticmethod
    def json_result(response):
        try:
            def unique(pairs):
                value = {}
                for key, item in pairs:
                    if key in value:
                        raise ValueError('duplicate key')
                    value[key] = item
                return value
            document = json.loads(response, object_pairs_hook=unique)
            result = document['result']
            if not isinstance(result, dict) or not isinstance(result['noticeList'], list):
                raise ValueError('missing rows')
            for key in ('currentPageNo', 'recordCountPerPage', 'totalRecordCount'):
                if type(result[key]) is not int or result[key] < (0 if key == 'totalRecordCount' else 1):
                    raise ValueError('invalid pagination')
            if len(result['noticeList']) > result['recordCountPerPage'] or len(result['noticeList']) > result['totalRecordCount']:
                raise ValueError('invalid row count')
            return result
        except (ValueError, TypeError, KeyError) as error:
            raise StructureError('UNVERIFIED_RIPC_JSON_RESPONSE') from error

    def parse_list(self, response):
        if isinstance(response, list) or not response.lstrip().startswith('{'):
            return super().parse_list(response)
        items = {}
        for row in self.json_result(response)['noticeList']:
            if not isinstance(row, dict) or row.get('noticeCode') not in ('NST001', 'NST002', 'NST003'):
                raise StructureError('INVALID_RIPC_NOTICE_ROW')
            if row['noticeCode'] == 'NST002':  # Template explicitly excludes drafts.
                continue
            try:
                identity = {key: str(row[key]) for key in self.identity_parameters}
                url = self.build_detail_url(self.detail_path + '?' + urlencode(identity))
                title = normalize_whitespace(html_to_content_text(row['noticeTitle']))
                if not title:
                    raise ValueError('empty title')
                raw_start, raw_end = row.get('startDateStr'), row.get('endDateStr')
                if raw_start in (None, '', '-') and raw_end in (None, '', '-'):
                    start, end = None, None
                else:
                    start, end = period(f'{raw_start} ~ {raw_end}', year=identity['bizYear'])
                category = normalize_whitespace(row.get('bizCategory1Name') or '')
                institution = normalize_whitespace(row.get('centerName') or '')
                item = NoticeLink(url, title, url, apply_start=start, apply_end=end,
                                  category=category if category not in ('', '-') else None,
                                  institution=institution if institution not in ('', '-') else None)
            except (KeyError, TypeError, ValueError) as error:
                raise StructureError('INVALID_RIPC_NOTICE_ROW') from error
            if url in items and items[url] != item:
                raise StructureError('CONFLICTING_DUPLICATE_NOTICE')
            items[url] = item
        return list(items.values())

    def extraction_body(self, root):
        body = root.find(id='elem')
        return body[0].html() if body else super().extraction_body(root)

    def detail_content(self, root):
        body = root.find(id='elem')
        if not body:
            return super().detail_content(root)
        if len(body) != 1:
            raise StructureError('AMBIGUOUS_RIPC_BODY')
        return body[0].text()

    def parse_detail(self, response, item):
        root = parse_html(response)
        values = parse_qs(urlsplit(item.url).query)
        forms = root.find('form', id='frmParams')
        if len(forms) > 1:
            raise StructureError('AMBIGUOUS_RIPC_IDENTITY_FORM')
        identity_scope = forms[0] if forms else root
        for key in self.identity_parameters:
            hidden = identity_scope.find('input', attr={'name': key})
            if hidden and (len(hidden) != 1 or hidden[0].attrs.get('value') != values[key][0]):
                raise StructureError('RIPC_DETAIL_IDENTITY_MISMATCH')
        parsed = super().parse_detail(response, item)
        institution = metadata(root, '수요기관')
        if institution is not None and institution.text():
            parsed = replace(parsed, link=replace(parsed.link, institution=institution.text()))
        return parsed
