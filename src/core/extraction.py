"""Bounded public-document extraction. No AI, company data or paid services.

Only successful blob/page OCR is cached; failed units are retried next run.
Cache keys include the extractor/engine policy as well as the source SHA256.
"""
from __future__ import annotations

import base64
import hashlib
import io
import logging
import re
import subprocess
import sys
import tempfile
import time
import zipfile
import zlib
from dataclasses import dataclass, replace
from html import unescape
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from src.core.normalizer import generate_content_hash
from src.core.storage import _atomic_json
from src.scrapers._html import parse_html

VERSION = 'extract-v1-tesseract5-kor-eng-psm6'
INCOMPLETE = '[추출 미완료: 원문 확인 필요]'
OCR_LABEL = '[OCR 추출: 날짜·참가 자격은 원문 대조 필요]'
MAX_BYTES = 25 * 1024 * 1024
MAX_PIXELS = 32_000_000
IMAGE_EXT = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tif', '.tiff'}
DOC_EXT = IMAGE_EXT | {'.pdf', '.hwp', '.hwpx', '.zip', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'}
LOG = logging.getLogger(__name__)


def failure(error, *, method=None):
    code = str(error) if re.fullmatch(r'[A-Z][A-Z0-9_]{1,80}',str(error)) else None
    if isinstance(error, subprocess.TimeoutExpired):
        code = 'PROCESS_TIME_LIMIT'
    value = dict(status='DEFERRED' if isinstance(error, TimeoutError) else 'FAILED',
                 text='',error=type(error).__name__,error_code=code)
    if method:
        value['method'] = method
    return value


@dataclass(frozen=True)
class Resource:
    url: str
    name: str = ''
    kind: str = 'attachment'


def discover(html, base_url, attachments=()):
    """Conservative discovery: uncertainty includes an image, never drops it.

    Explicitly named logo/icon/spacer assets are the only filename exclusions.
    Editor HTML inside hidden attributes is also observed on KISTA.
    """
    root = parse_html(html)
    for node in list(root.find('input')) + list(root.find('textarea')):
        if node.attrs.get('name', '').lower() in {'contents', 'content'}:
            root.children.extend(parse_html(unescape(node.attrs.get('value', '') or node.text())).children)
    result = {}
    def add(url, name='', kind='attachment'):
        url = url.strip()
        if not url:
            return
        target = url if url.startswith('data:image/') else urljoin(base_url, url)
        if urlsplit(target).scheme not in {'http', 'https', 'data'}:
            return
        if not target.startswith('data:'):
            target = quote(target, safe=':/?&=%+#@;,$!()*[]~')
        result.setdefault(target, Resource(target, name, kind))
    for node in root.find():
        action = node.attrs.get('onclick','').strip()
        href = node.attrs.get('href','')
        if (action and re.search(r'download|fileDown|첨부파일 다운로드',action+' '+node.attrs.get('title',''),re.I)
                and (not href or href.startswith(('#','javascript:')))):
            key = 'unresolved:' + hashlib.sha256(action.encode()).hexdigest()
            result[key] = Resource(key,node.text(),'unresolved_attachment')
        if node.tag in {'img', 'source', 'image'}:
            src = (node.attrs.get('data-src') or node.attrs.get('data-original') or
                   node.attrs.get('data-lazy-src') or node.attrs.get('src') or
                   node.attrs.get('href') or node.attrs.get('xlink:href', ''))
            filename = Path(urlsplit(src).path).stem.lower()
            decorative = re.fullmatch(r'(?:logo|icon|ico|spacer|blank|bullet|btn)(?:[_-].*)?', filename)
            if decorative:
                continue
            add(src, node.attrs.get('alt', ''), 'image')
            for entry in node.attrs.get('srcset', '').split(','):
                if entry.strip():
                    add(entry.strip().split()[0], kind='image')
        elif node.tag in {'a', 'object', 'embed'}:
            href = node.attrs.get('href') or node.attrs.get('data') or node.attrs.get('src', '')
            name = node.text()
            if (Path(unquote(urlsplit(href).path)).suffix.lower() in DOC_EXT
                    or re.search(r'fileDown|download|/FILE_|atchFile', href, re.I)
                    or any(ext in name.lower() for ext in DOC_EXT)):
                add(href, name)
        for url in re.findall(r'url\(\s*[\'\"]?([^\'\")]+)',node.attrs.get('style',''),re.I):
            add(url,kind='image')
    for url in attachments:
        add(url)
    return list(result.values())


def download(resource):
    if resource.url.startswith('data:image/'):
        header, payload = resource.url.split(',', 1)
        if ';base64' not in header or len(payload) > MAX_BYTES * 4 // 3 + 8:
            raise ValueError('INLINE_IMAGE_LIMIT_OR_ENCODING')
        data = base64.b64decode(payload, validate=True)
        name = resource.name
    else:
        request = Request(resource.url, headers={'User-Agent': 'NoticeMonitor/0.2', 'Accept-Encoding': 'identity'})
        with urlopen(request, timeout=15) as response:
            size = response.headers.get('Content-Length')
            if size and int(size) > MAX_BYTES:
                raise ValueError('ATTACHMENT_BYTE_LIMIT')
            chunks, total = [], 0
            deadline = time.monotonic() + 45
            while True:
                if time.monotonic() > deadline:
                    raise TimeoutError('DOWNLOAD_TIME_LIMIT')
                chunk = response.read1(min(65536, MAX_BYTES + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk); total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError('ATTACHMENT_BYTE_LIMIT')
            data = b''.join(chunks)
            name = response.headers.get_filename() or resource.name or urlsplit(resource.url).path
    if len(data) > MAX_BYTES:
        raise ValueError('ATTACHMENT_BYTE_LIMIT')
    return data, name


class Tesseract:
    def __call__(self, data):
        # Decode before invoking the executable to reject decompression bombs.
        from PIL import Image, ImageOps, ImageSequence
        Image.MAX_IMAGE_PIXELS = MAX_PIXELS
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > MAX_PIXELS:
                raise ValueError('IMAGE_PIXEL_LIMIT')
            if getattr(image, 'n_frames', 1) > 20:
                raise ValueError('IMAGE_FRAME_LIMIT')
            frames, pixels = [], 0
            for frame in ImageSequence.Iterator(image):
                pixels += frame.width * frame.height
                if pixels > MAX_PIXELS:
                    raise ValueError('IMAGE_TOTAL_PIXEL_LIMIT')
                frames.append(ImageOps.exif_transpose(frame).convert('RGB'))
            with tempfile.TemporaryDirectory(prefix='notice-ocr-') as tmp:
                path = Path(tmp) / ('input.tiff' if len(frames)>1 else 'input.png')
                frames[0].save(path,save_all=True,append_images=frames[1:]) if len(frames)>1 else frames[0].save(path)
                result = subprocess.run(['tesseract', str(path), 'stdout', '-l', 'kor+eng', '--psm', '6'],
                                        capture_output=True, timeout=45, check=True)
        text = result.stdout.decode('utf-8').strip()
        if not text:
            raise ValueError('OCR_EMPTY')
        return text


class ExtractionQueue:
    """Discover while collecting, then prioritize new/changed notices centrally."""
    def __init__(self):
        self.resources = {}

    def enrich(self, notice, resources):
        previous = self.resources.get(notice.notice_id, [])
        self.resources[notice.notice_id] = list({r.url:r for r in [*previous,*resources]}.values())
        return notice


class Extractor:
    def __init__(self, cache_dir, *, ocr=None, fetch=None, budget_seconds=720, pages_per_run=20, isolated=False):
        self.cache_root = Path(cache_dir)
        self.cache_dir = Path(cache_dir) / VERSION
        self.ocr = ocr or Tesseract()
        self.fetch = fetch or download
        self.deadline = time.monotonic() + budget_seconds
        self.pages_per_run = pages_per_run
        self.metrics = {}
        self.isolated = isolated

    def _read(self, key):
        import json
        try:
            return json.loads((self.cache_dir / (key + '.json')).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None

    def _save(self, key, value):
        _atomic_json(self.cache_dir / (key + '.json'), value)

    def _check_time(self):
        if time.monotonic() >= self.deadline:
            raise TimeoutError('RUN_BUDGET_DEFERRED')

    def image(self, data):
        key = 'image-' + hashlib.sha256(data).hexdigest()
        cached = self._read(key)
        if cached:
            return dict(cached, cache_hit=True)
        self._check_time()
        try:
            text = self.ocr(data)
            result = dict(status='SUCCESS', method='OCR', text=text, cache_hit=False)
            self._save(key, result)
            return result
        except Exception as error:
            return failure(error,method='OCR')

    def _unit(self, data):
        try:
            return self.image(data)
        except Exception as error:
            return failure(error,method='OCR')

    def pdf(self, data, key):
        import pymupdf
        progress = self._read(key + '-pages') or {}
        attempted = 0
        with pymupdf.open(stream=data, filetype='pdf') as doc:
            for index in range(len(doc)):
                page_key = str(index + 1)
                if progress.get(page_key, {}).get('status') == 'SUCCESS':
                    continue
                if attempted >= self.pages_per_run or time.monotonic() >= self.deadline:
                    break
                attempted += 1
                page = doc[index]
                parts = [dict(method='DIRECT', text=page.get_text(), status='SUCCESS')]
                # Mixed text/image PDFs must OCR their images even with ample text.
                images = page.get_images(full=True)
                for xref in dict.fromkeys(item[0] for item in images):
                    try:
                        dimensions = next(item for item in images if item[0] == xref)
                        if dimensions[2] * dimensions[3] > MAX_PIXELS:
                            raise ValueError('PDF_IMAGE_PIXEL_LIMIT')
                        parts.append(self._unit(doc.extract_image(xref)['image']))
                    except Exception as error:
                        parts.append(failure(error,method='OCR'))
                if not parts[0]['text'].strip() and not images:
                    scale = min(200 / 72, (MAX_PIXELS / max(1, page.rect.width * page.rect.height)) ** .5)
                    parts.append(self._unit(page.get_pixmap(matrix=pymupdf.Matrix(scale, scale)).tobytes('png')))
                progress[page_key] = dict(status='SUCCESS' if all(p['status']=='SUCCESS' for p in parts) else 'PARTIAL', parts=parts)
                self._save(key + '-pages', progress)
            parts = [dict(p, page=int(i)) for i, value in sorted(progress.items(), key=lambda x:int(x[0])) for p in value['parts']]
            complete = len(progress) == len(doc) and all(p['status']=='SUCCESS' for p in progress.values())
            return dict(status='SUCCESS' if complete else 'PARTIAL', parts=parts,
                        pages_total=len(doc), pages_processed=len(progress))

    def hwpx(self, data):
        parts = []
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > 2000 or sum(i.file_size for i in infos) > MAX_BYTES * 4:
                raise ValueError('ARCHIVE_EXPANSION_LIMIT')
            for info in infos:
                self._check_time()
                name = info.filename
                if name.startswith('Contents/') and name.endswith('.xml'):
                    root = ElementTree.fromstring(archive.read(info))
                    text = '\n'.join(n.text for n in root.iter() if n.tag.rsplit('}',1)[-1]=='t' and n.text)
                    parts.append(dict(method='DIRECT', text=text, status='SUCCESS', member=name))
                elif name.lower().startswith('bindata/'):
                    unit = self._unit(archive.read(info))
                    parts.append(dict(unit, member=name))
        return dict(status='SUCCESS' if parts and all(p['status']=='SUCCESS' for p in parts) else 'PARTIAL', parts=parts)

    def hwp(self, data):
        import olefile
        parts = []
        with olefile.OleFileIO(io.BytesIO(data)) as ole:
            header = ole.openstream('FileHeader').read()
            flags = int.from_bytes(header[36:40], 'little')
            if flags & 2:
                raise ValueError('ENCRYPTED_HWP')
            for path in ole.listdir():
                if path[0] not in {'BodyText', 'BinData'}:
                    continue
                self._check_time()
                raw = ole.openstream(path).read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise ValueError('HWP_STREAM_LIMIT')
                if flags & 1:
                    decoder = zlib.decompressobj(-15)
                    try:
                        decoded = decoder.decompress(raw, MAX_BYTES + 1)
                    except zlib.error:
                        if path[0] != 'BinData':
                            raise
                        decoded = raw # BinData can override document compression.
                    raw = decoded
                    if len(raw) > MAX_BYTES or decoder.unconsumed_tail:
                        raise ValueError('HWP_EXPANSION_LIMIT')
                if path[0] == 'BinData':
                    parts.append(dict(self._unit(raw), member='/'.join(path)))
                else:
                    pos, text = 0, []
                    while pos + 4 <= len(raw):
                        record = int.from_bytes(raw[pos:pos+4], 'little'); pos += 4
                        size = record >> 20
                        if size == 4095:
                            size = int.from_bytes(raw[pos:pos+4], 'little'); pos += 4
                        if (record & 1023) == 67:
                            text.append(re.sub(r'[\x00-\x08\x0b-\x1f]', '', raw[pos:pos+size].decode('utf-16le', errors='replace')))
                        pos += size
                    parts.append(dict(method='DIRECT', status='SUCCESS', text='\n'.join(text), member='/'.join(path)))
        return dict(status='SUCCESS' if parts and all(p['status']=='SUCCESS' for p in parts) else 'PARTIAL', parts=parts)

    def document(self, data, name='', kind='attachment'):
        if self.isolated:
            self._check_time()
            self.cache_root.mkdir(parents=True, exist_ok=True)
            # Native PDF/image parsers and OCR cannot stall the whole collector.
            with tempfile.TemporaryDirectory(dir=self.cache_root, prefix='worker-') as tmp:
                path = Path(tmp).resolve()
                (path/'input').write_bytes(data)
                import json
                options = dict(cache=str(self.cache_root.resolve()), name=name, kind=kind,
                               budget=max(1,self.deadline-time.monotonic()), pages=self.pages_per_run)
                (path/'options.json').write_text(json.dumps(options),encoding='utf-8')
                subprocess.run([sys.executable,'-m','src.core.extraction_worker',str(path)],
                               timeout=min(120, max(1,self.deadline-time.monotonic())),
                               check=True,capture_output=True)
                return json.loads((path/'result.json').read_text(encoding='utf-8'))
        key = 'file-' + hashlib.sha256(data).hexdigest()
        cached = self._read(key)
        if cached:
            return dict(cached, cache_hit=True)
        self._check_time()
        if data.startswith(b'%PDF'):
            result = self.pdf(data, key)
        elif data.startswith(b'PK') and (name.lower().endswith('.hwpx') or b'Contents/' in data):
            result = self.hwpx(data)
        elif data.startswith(bytes.fromhex('d0cf11e0a1b11ae1')):
            result = self.hwp(data)
        elif kind == 'image' or Path(name).suffix.lower() in IMAGE_EXT or data.startswith((b'\x89PNG', b'\xff\xd8', b'RIFF', b'GIF8')):
            result = dict(parts=[self._unit(data)])
            result['status'] = result['parts'][0]['status']
        else:
            result = dict(status='UNSUPPORTED', parts=[])
        result['sha256'] = hashlib.sha256(data).hexdigest()
        if result['status'] == 'SUCCESS':
            self._save(key, result)
        return result

    def enrich(self, notice, resources):
        started = time.monotonic()
        records = []
        original = notice.content_text
        if original.startswith('[이미지 본문:') or original == INCOMPLETE:
            original = ''
        chunks = [('[HTML 원문 직접 추출] ' if resources else '') + original] if original else []
        seen = set(' '.join(line.split()) for line in re.split(r'\n|(?<=[.!?])\s+', original) if line.strip())
        metrics = self.metrics.setdefault(notice.source_id, dict(targets=0, success=0, failed=0, partial=0, deferred=0, unsupported=0, cache_hits=0, ocr_targets=0, ocr_success=0, ocr_failed=0, ocr_characters=0, elapsed_seconds=0))
        for resource in resources:
            metrics['targets'] += 1
            try:
                self._check_time()
                if resource.url.startswith('unresolved:'):
                    result = dict(status='UNSUPPORTED',parts=[],error='UNRESOLVED_ATTACHMENT_LINK')
                else:
                    data, name = self.fetch(resource)
                    result = self.document(data, name, resource.kind)
            except Exception as error:
                result = dict(failure(error),parts=[])
            metrics[result['status'].lower()] += 1
            metrics['cache_hits'] += int(result.get('cache_hit', False))
            # Inline payloads stay out of Notice/history; HTTP source links are
            # retained privately for provenance and retries beyond list windows.
            identity = hashlib.sha256(resource.url.encode()).hexdigest()
            records.append(dict(result, resource_id=identity, kind=resource.kind,
                                source_url=resource.url if not resource.url.startswith('data:') else None,
                                name=resource.name))
            for part in result.get('parts', []):
                lines = []
                for line in part.get('text', '').splitlines():
                    line = ' '.join(line.split())
                    if line and line not in seen:
                        lines.append(line); seen.add(line)
                if part.get('method') == 'OCR':
                    metrics['ocr_targets'] += 1
                    metrics['ocr_success' if part['status']=='SUCCESS' else 'ocr_failed'] += 1
                    metrics['ocr_characters'] += len(part.get('text', ''))
                if lines:
                    label = OCR_LABEL if part['method']=='OCR' else '[첨부 원문 직접 추출]'
                    source = result.get('sha256', identity)[:16]
                    location = str(part.get('page') or part.get('member') or '')
                    chunks.append(f'{label} source={source} {location}\n' + '\n'.join(lines))
        complete = all(r['status']=='SUCCESS' for r in records) and bool(original.strip() or
            any(p.get('text','').strip() for r in records for p in r.get('parts',[])))
        if not complete:
            chunks.append(INCOMPLETE)
        text = '\n'.join(chunks)
        metrics['elapsed_seconds'] += round(time.monotonic()-started, 3)
        LOG.info('notice_extraction source_id=%s resources=%d complete=%s elapsed=%.3f', notice.source_id, len(records), complete, time.monotonic()-started)
        return replace(notice, content_text=text, content_hash=generate_content_hash(content_text=text),
                       extraction=dict(version=VERSION, original_hash=notice.content_hash, original_text=original,
                                       status='SUCCESS' if complete else 'PARTIAL', resources=records))
