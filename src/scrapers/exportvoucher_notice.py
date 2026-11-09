"""Exportvoucher public notices and anonymous, session-bound file downloads.

The official ftFile2 widget calls File2List by docId in the detail page's
anonymous browser session. File secCodes are session issued, never
durable identities. Only file_id is retained in extraction work manifests;
download() reopens the public notice and resolves a fresh browser session.
"""
from dataclasses import dataclass, replace
from html import escape
from http.cookiejar import CookieJar
import json
import re
import time
from pathlib import PurePosixPath
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener

from src.scrapers._board import BoardScraper, NoticeLink, date_field
from src.scrapers._html import StructureError, parse_html

BASE = 'https://www.exportvoucher.com'
LIST = BASE + '/portal/board/boardList?bbs_id=1'
FILE_PATH = '/common.FileDownload.do'


def public_url(url, path):
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.netloc != 'www.exportvoucher.com' or parts.path != path or parts.fragment:
        raise StructureError('UNEXPECTED_EXPORTVOUCHER_URL')
    return parse_qs(parts.query)


def notice_url(identity):
    return BASE + '/portal/board/boardView?' + urlencode({'bbs_id': '1', 'ntt_id': identity})


@dataclass(frozen=True)
class PublicAttachment:
    file_id: str
    name: str
    size: int
    sec_code: str

    @property
    def resource_url(self):
        # Stable private queue identity, resolved by the source-specific fetcher.
        return BASE + FILE_PATH + '?' + urlencode({'file_id': self.file_id})

    @property
    def download_url(self):
        return BASE + FILE_PATH + '?' + urlencode({'file_id': self.file_id, 'sec_code': self.sec_code})


def attachment_groups(html):
    scope = parse_html(html).one('div', cls='bbsViewArea')
    groups = []
    for node in (n for n in scope.find() if 'data-file-download' in n.attrs):
        value = node.attrs.get('data-doc-id', '')
        if not re.fullmatch(r'DOC_[0-9]+', value):
            raise StructureError('INVALID_EXPORTVOUCHER_DOC_ID')
        if value not in groups:
            groups.append(value)
    # No file widget is the observed no-attachment representation. A widget
    # returning [] is not proof of no attachments: this was the original bug.
    return groups


def parse_file_list(text):
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        raise StructureError('EXPORTVOUCHER_FILE_LIST_NOT_JSON') from None
    if not isinstance(data, list) or not data or len(data) > 100:
        raise StructureError('EXPORTVOUCHER_EMPTY_OR_INVALID_FILE_GROUP')
    result = {}
    for row in data:
        if (not isinstance(row, dict)
            or not isinstance(row.get('fileId'), str) or not re.fullmatch(r'FILE_[0-9]+', row['fileId'])
            or not isinstance(row.get('fileName'), str) or not row['fileName'].strip()
            or any(ord(c) < 32 for c in row['fileName'])
            or type(row.get('fileSize')) is not int or row['fileSize'] <= 0
            or not isinstance(row.get('secCode'), str) or not re.fullmatch(r'[A-Za-z0-9]{1,128}', row['secCode'])):
            raise StructureError('INVALID_EXPORTVOUCHER_FILE_METADATA')
        item = PublicAttachment(row['fileId'], row['fileName'], row['fileSize'], row['secCode'])
        if item.file_id in result and result[item.file_id] != item:
            raise StructureError('CONFLICTING_EXPORTVOUCHER_FILE_ID')
        result[item.file_id] = item
    return list(result.values())


def validate_attachment(data, name, content_type, expected_size):
    if not data:
        raise ValueError('EXPORTVOUCHER_EMPTY_DOWNLOAD')
    if content_type in {'text/html', 'application/xhtml+xml', 'application/json'} or data.lstrip()[:32].lower().startswith((b'<!doctype', b'<html', b'<script', b'<body')):
        raise ValueError('EXPORTVOUCHER_ERROR_DOCUMENT')
    extension = PurePosixPath(name).suffix.lower()
    ole = data.startswith(bytes.fromhex('d0cf11e0a1b11ae1'))
    zipped = data.startswith(b'PK\x03\x04')
    signatures = {'.pdf': data.lstrip().startswith(b'%PDF-'), '.hwp': ole,
        '.hwpx': zipped, '.zip': zipped, '.docx': zipped, '.xlsx': zipped, '.pptx': zipped,
        '.doc': ole, '.xls': ole, '.ppt': ole,
        '.png': data.startswith(b'\x89PNG\r\n\x1a\n'), '.jpg': data.startswith(b'\xff\xd8\xff'),
        '.jpeg': data.startswith(b'\xff\xd8\xff'), '.gif': data.startswith((b'GIF87a', b'GIF89a')),
        '.bmp': data.startswith(b'BM'), '.webp': data.startswith(b'RIFF') and data[8:12]==b'WEBP',
        '.tif': data.startswith((b'II*\x00',b'MM\x00*')), '.tiff': data.startswith((b'II*\x00',b'MM\x00*'))}
    if not signatures.get(extension, False):
        raise ValueError('EXPORTVOUCHER_INVALID_FILE_SIGNATURE')
    if len(data) != expected_size:
        raise ValueError('EXPORTVOUCHER_FILE_SIZE_MISMATCH')


class ExportVoucherSession:
    """One anonymous cookie jar. No login, token forgery or raw-file storage."""
    def __init__(self, *, opener=None):
        self.opener = opener if opener is not None else build_opener(HTTPCookieProcessor(CookieJar()))
        self.detail_url = None
        self.files = None
        self.ajax_nonce = int(time.time()*1000)

    def get(self, url, *, timeout, headers):
        parts = urlsplit(url)
        if parts.scheme != 'https' or parts.netloc != 'www.exportvoucher.com':
            raise StructureError('UNEXPECTED_EXPORTVOUCHER_ORIGIN')
        options = dict(headers)
        if parts.path == '/common/File2List':
            if not self.detail_url:
                raise StructureError('EXPORTVOUCHER_DETAIL_SESSION_REQUIRED')
            options.update({'X-Requested-With': 'XMLHttpRequest', 'Referer': self.detail_url, 'Accept': 'application/json'})
        with self.opener.open(Request(url, headers=options), timeout=timeout) as response:
            if urlsplit(response.url).netloc != 'www.exportvoucher.com' or urlsplit(response.url).path != parts.path:
                raise StructureError('EXPORTVOUCHER_UNEXPECTED_REDIRECT')
            data = response.read(3_000_001)
            if len(data) > 3_000_000:
                raise ValueError('EXPORTVOUCHER_TEXT_LIMIT')
            text = data.decode(response.headers.get_content_charset() or 'utf-8')
        if parts.path == '/portal/board/boardView':
            self.detail_url = url
        return text

    def list_attachments(self, html, *, request_text=None):
        get = request_text or (lambda url: self.get(url, timeout=25, headers={'User-Agent': 'NoticeMonitor/0.2'}))
        files = {}
        for doc in attachment_groups(html):
            # ftFile2.js explicitly sets jQuery cache:false. jQuery 1.9.1
            # appends a fresh _ nonce to GET requests; do not replay a cached
            # session-bound file list / secCode from the bare docId URL.
            self.ajax_nonce += 1
            for item in parse_file_list(get(BASE+'/common/File2List?'+urlencode({'docId': doc,'_':self.ajax_nonce}))):
                if item.file_id in files and files[item.file_id] != item:
                    raise StructureError('CONFLICTING_EXPORTVOUCHER_FILE_GROUP')
                files[item.file_id] = item
        return list(files.values())

    def download(self, resource, *, notice):
        from src.core.extraction import MAX_BYTES
        query = public_url(resource.url, FILE_PATH)
        ids = query.get('file_id', [])
        if set(query) != {'file_id'} or len(ids) != 1 or not re.fullmatch(r'FILE_[0-9]+', ids[0]):
            raise StructureError('INVALID_EXPORTVOUCHER_RESOURCE_ID')
        context = public_url(notice.url, '/portal/board/boardView')
        if context.get('bbs_id') != ['1'] or len(context.get('ntt_id', [])) != 1 or not context['ntt_id'][0].isdecimal():
            raise StructureError('INVALID_EXPORTVOUCHER_NOTICE_CONTEXT')
        if self.detail_url != notice.url or self.files is None:
            html = self.get(notice.url, timeout=25, headers={'User-Agent': 'NoticeMonitor/0.2'})
            self.files = self.list_attachments(html)
        item = next((f for f in self.files if f.file_id == ids[0]), None)
        if item is None:
            raise ValueError('EXPORTVOUCHER_FILE_NOT_IN_PUBLIC_NOTICE')
        if item.size > MAX_BYTES:
            raise ValueError('ATTACHMENT_BYTE_LIMIT')
        request = Request(item.download_url, headers={'User-Agent': 'NoticeMonitor/0.2',
                          'Referer': notice.url, 'Accept-Encoding': 'identity'})
        with self.opener.open(request, timeout=15) as response:
            public_url(response.url, FILE_PATH)
            chunks, total, deadline = [], 0, time.monotonic()+45
            while True:
                if time.monotonic() > deadline:
                    raise TimeoutError('DOWNLOAD_TIME_LIMIT')
                chunk = response.read1(min(65536, MAX_BYTES+1-total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError('ATTACHMENT_BYTE_LIMIT')
            data = b''.join(chunks)
            validate_attachment(data, item.name, response.headers.get_content_type(), item.size)
        return data, item.name


class ExportVoucherScraper(BoardScraper):
    source = 'exportvoucher_notice'

    def __init__(self, config, **kwargs):
        if kwargs.get('transport') is None:
            kwargs['transport'] = ExportVoucherSession()
        super().__init__(config, **kwargs)
        self.attachment_session = self.transport if isinstance(self.transport, ExportVoucherSession) else ExportVoucherSession()
        self.attachment_results = {}

    def parse_list(self, response):
        table = parse_html(response).one('table', cls='table-default mT10')
        if not all(word in table.one('thead').text() for word in ('제목', '등록일')):
            raise StructureError('CHANGED_EXPORTVOUCHER_LIST')
        result = {}
        for row in table.one('tbody').elements('tr'):
            cells = row.elements('td')
            if len(cells) != 4:
                raise StructureError('CHANGED_EXPORTVOUCHER_LIST_COLUMNS')
            anchor = cells[1].one('a')
            match = re.fullmatch(r'goDetail\(([0-9]+)\)', anchor.attrs.get('onclick', ''))
            if not match:
                raise StructureError('INVALID_EXPORTVOUCHER_NOTICE_ID')
            result.setdefault(match[1], NoticeLink(match[1], anchor.text(), notice_url(match[1]), date_field(cells[2].text())))
        if not result:
            raise StructureError('UNVERIFIED_EMPTY_EXPORTVOUCHER_LIST')
        return list(result.values())

    def page_links(self, response):
        pages = {}
        for anchor in parse_html(response).find('a'):
            match = re.fullmatch(r'_pageCommon_goPage\(([1-9][0-9]*)\);', anchor.attrs.get('onclick', ''))
            if match and anchor.text().isdecimal() and int(anchor.text()) == int(match[1]):
                pages[int(match[1])] = LIST+'&pageNo='+match[1]
        return [pages[p] for p in sorted(pages)]

    def fetch_detail(self, item):
        html = super().fetch_detail(item)
        # Resolve only the notice widget, not the site's global policy downloads.
        files = self.attachment_session.list_attachments(html, request_text=self.request_text)
        self.attachment_results[item.source_notice_id] = files
        return html

    def parse_detail(self, response, item):
        root = parse_html(response)
        scope = root.one('div', cls='bbsViewArea')
        parsed = self.detail(item, scope.one('div', cls='bbsInfo').one('h3'), scope.one('div', cls='bbsCon'))
        if item.source_notice_id not in self.attachment_results:
            if attachment_groups(response):
                raise StructureError('EXPORTVOUCHER_ATTACHMENTS_NOT_RESOLVED')
            self.attachment_results[item.source_notice_id] = []
        links = ''.join(f'<a href="{escape(f.resource_url, quote=True)}">{escape(f.name)}</a>'
                        for f in self.attachment_results[item.source_notice_id])
        return replace(parsed, body_html=parsed.body_html+links)

    def parse_attachments(self, response):
        # Already resolved into scoped body_html, with filenames and stable IDs.
        return []
