"""KISTA ac board: explicit view(year,id), POST pager and DEXT5 metadata."""

import re
from html import unescape
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

from ._portal import PortalScraper
from ._html import StructureError, parse_html
from src.core.normalizer import html_to_content_text, normalize_url


class KistaScraper(PortalScraper):
    source = 'kista_ippro'
    detail_path = '/ippro/com/iprndMain/selectBusinessAnnounceView.do'
    identity_parameters = ('annYy', 'annId')
    detail_query = {'bbsType': 'ac'}
    headers = ('번호', '구분', '공고명', '조회수', '접수기간')
    title_label = '공고명'
    category_label = '구분'
    period_label = '접수기간'
    detail_category_label = '사업구분'

    def list_form(self, root):
        forms = root.find('form', attr={'name': 'frm'})
        if not forms:
            return None
        if len(forms) != 1:
            raise StructureError('AMBIGUOUS_KISTA_FORM')
        form = forms[0]
        if (form.attrs.get('method', '').lower() != 'post'
                or form.attrs.get('action') != '/ippro/com/iprndMain/selectBusinessAnnounceList.do'):
            raise StructureError('CHANGED_KISTA_FORM')
        fields = {}
        allowed = {'pageIndex', 'DepthCode1', 'DepthCode2', 'bbsType', 'annYy', 'annId', 'searchGubunCd', 'searchWrd'}
        for node in form.find():
            name = node.attrs.get('name')
            if node.tag not in ('input', 'select') or name not in allowed:
                continue
            if name in fields:
                raise StructureError('DUPLICATE_KISTA_FORM_FIELD')
            value = node.attrs.get('value', '')
            if node.tag == 'select':
                options = node.find('option')
                selected = [option for option in options if 'selected' in option.attrs]
                if len(selected) > 1 or not options:
                    raise StructureError('INVALID_KISTA_SELECT')
                value = (selected or options)[0].attrs.get('value', '')
            fields[name] = value
        if set(fields) != allowed or fields['bbsType'] != 'ac' or not fields['pageIndex'].isdecimal():
            raise StructureError('INCOMPLETE_KISTA_FORM')
        return fields

    @staticmethod
    def _validate_script(html):
        # Execute no JavaScript; accept only the literal actions seen in source.
        for function, path in (('view', '/ippro/com/iprndMain/selectBusinessAnnounceView.do'),
                               ('fn_egov_select_noticeList', '/ippro/com/iprndMain/selectBusinessAnnounceList.do')):
            match = re.search(r'function\s+' + function + r'\([^)]*\)\s*\{([^}]+)\}', html)
            if match is None or f'"{path}"' not in match[1] or 'document.frm.submit()' not in match[1]:
                raise StructureError('CHANGED_KISTA_SCRIPT')
            required = ('document.frm.annYy.value = annYy', 'document.frm.annId.value = annId') if function == 'view' else ('document.frm.pageIndex.value = pageNo',)
            if not all(value in match[1] for value in required):
                raise StructureError('CHANGED_KISTA_SCRIPT_FIELDS')

    def parse_list(self, response):
        if isinstance(response, list):
            return super().parse_list(response)
        root = parse_html(response)
        fields = self.list_form(root)
        if fields is None:
            return super().parse_list(response)
        self._validate_script(response)
        table = self._table(root)
        urls = []
        for row in table.find('tr'):
            cells = row.elements('td')
            if len(cells) != len(self.headers):
                continue  # Base parser validates empty/changed rows.
            for anchor in cells[2].find('a'):
                match = re.fullmatch(r"javascript:view\('([0-9]{4})','([0-9]+)'\);?", anchor.attrs.get('href', ''))
                if match is None:
                    raise StructureError('UNVERIFIED_KISTA_DETAIL_CALL')
                url = self.build_detail_url(self.detail_path + '?' + urlencode({'annYy': match[1], 'annId': match[2], 'bbsType': fields['bbsType']}))
                anchor.attrs['href'] = url
                urls.append(url)
        items = super().parse_list(root.html())
        if not hasattr(self, '_detail_forms'):
            self._detail_forms = {}
        self._detail_forms.update({url: dict(fields) for url in urls})
        return items

    def pagination_pages(self, html):
        root = parse_html(html)
        self._validate_script(html)
        fields = self.list_form(root)
        if fields is None:
            raise StructureError('MISSING_KISTA_POST_FORM')
        pagers = root.find('div', cls='page')
        if len(pagers) != 1:
            raise StructureError('CHANGED_KISTA_PAGER')
        pages = set()
        for anchor in pagers[0].find('a'):
            match = re.fullmatch(r"\s*fn_egov_select_noticeList\(\s*['\"]?([0-9]+)['\"]?\s*\);?\s*", anchor.attrs.get('onclick', ''))
            if anchor.attrs.get('href') != '#' or match is None or int(match[1]) < 1:
                raise StructureError('UNVERIFIED_KISTA_PAGER_CALL')
            pages.add(int(match[1]))
        return sorted(pages)

    def _fetch_pages(self, first, first_html):
        fields = self.list_form(parse_html(first_html))
        if fields is None:
            return super()._fetch_pages(first, first_html)
        endpoint = urljoin(first, '/ippro/com/iprndMain/selectBusinessAnnounceList.do')
        queue, pages, visited = [first_html], [first_html], {int(fields['pageIndex'])}
        pending = []
        for html in queue:
            items = self.parse_list(html)
            if self.list_page_complete(items):
                return pages
            form = self.list_form(parse_html(html))
            for page in self.pagination_pages(html):
                if page not in visited and page not in pending:
                    pending.append(page)
            if pending:
                if not self.may_fetch_list_page(len(pages)):
                    self.logger.warning('pagination_window_capped source_id=%s max_pages=%d', self.source_id, self.max_pages)
                    return pages
                page = pending.pop(0)
                data = {**form, 'pageIndex': str(page)}
                response = self.request_form(self._allowed(endpoint), data)
                returned = self.list_form(parse_html(response))
                if returned is None or returned['pageIndex'] != str(page):
                    raise StructureError('KISTA_PAGE_RESPONSE_MISMATCH')
                self.parse_list(response)
                pages.append(response)
                queue.append(response)
                visited.add(page)
        return pages

    def fetch_detail(self, item):
        form = getattr(self, '_detail_forms', {}).get(item.url)
        if form is None:
            return super().fetch_detail(item)
        query = parse_qs(urlsplit(item.url).query)
        data = {**form, 'annYy': query['annYy'][0], 'annId': query['annId'][0]}
        return self.request_form(self._allowed(urljoin(item.url, self.detail_path)), data)

    def detail_scope(self, response):
        root = parse_html(response)
        tables = root.find('table', cls='infor-view')
        if not tables:
            return root  # Legacy direct-link regression samples.
        if len(tables) != 1:
            raise StructureError('AMBIGUOUS_KISTA_DETAIL')
        boards = root.find('input', attr={'name': 'bbsType'})
        if len(boards) != 1 or boards[0].attrs.get('value') != 'ac':
            raise StructureError('UNEXPECTED_KISTA_DETAIL_BOARD')
        return tables[0]

    def detail_content(self, root):
        inputs = root.find('input', attr={'name': 'contents'})
        if not inputs:
            return super().detail_content(root)
        if len(inputs) != 1:
            raise StructureError('AMBIGUOUS_KISTA_BODY')
        # Attribute entity decoding + the extra &quot; pass in editorInit.
        # Image-only body remains empty text; no OCR/AI/network requests.
        return html_to_content_text(unescape(inputs[0].attrs.get('value', '')))

    def extraction_body(self, root):
        inputs = root.find('input', attr={'name': 'contents'})
        if inputs:
            return unescape(inputs[0].attrs.get('value', ''))
        return super().extraction_body(root)

    def parse_attachments(self, response):
        links = list(super().parse_attachments(response))
        root = parse_html(response)
        scripts = [child for node in root.find('script') for child in node.children if isinstance(child, str)]
        for script in scripts:
            function = re.search(r'function\s+DEXT5UPLOAD_OnCreationComplete\(\)\s*\{([^}]+)\}', script)
            if function is None:
                continue
            calls = re.findall(r'DEXT5UPLOAD\.AddUploadedFile\(([^\n]+)\);', function[1])
            if len(calls) != function[1].count('DEXT5UPLOAD.AddUploadedFile'):
                raise StructureError('UNVERIFIED_DEXT5_ATTACHMENT')
            for call in calls:
                match = re.fullmatch(r"'([0-9]+)',\s*'([^']*)',\s*((?:'[^']*'\s*\+\s*)*'[^']*'),\s*'[0-9]+',\s*'',\s*G_UploadID", call.strip())
                if match is None:
                    raise StructureError('UNVERIFIED_DEXT5_ATTACHMENT')
                path = ''.join(re.findall(r"'([^']*)'", match[3]))
                if not re.fullmatch(r'/iprnd_data/RND-IP2_DATA/AN/FILE_[0-9]+', path):
                    raise StructureError('UNEXPECTED_DEXT5_FILE_PATH')
                url = normalize_url(urljoin(self.config['list_url'], path))
                if url not in links:
                    links.append(url)
        return tuple(links)
