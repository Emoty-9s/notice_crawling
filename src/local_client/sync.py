"""M12 public feed sync with a single atomic cache snapshot (stdlib only)."""

from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from http.client import HTTPException
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen
from src.core.retention import retention_date
from src.core.eligibility import PUBLIC_SCHEMA_VERSION, deadline_state


DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[2] / 'local' / 'cache'
MAX_DOWNLOAD_BYTES = 16 * 1024 * 1024
NOTICE_FIELDS = frozenset({
    'notice_id', 'source_id', 'institution', 'title', 'category', 'participation_type',
    'published_at', 'apply_start', 'apply_end', 'url', 'summary', 'keywords',
    'relevance_reason', 'first_seen_at', 'updated_at', 'is_new',
})


class SyncError(Exception):
    """Fixed diagnostic code, without response bodies or raw network errors."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class SyncResult:
    status: str  # UPDATED, UNCHANGED or FALLBACK
    feed: dict
    metadata: dict
    error_code: str | None = None


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def _constant(value):
    raise ValueError('nonstandard JSON constant')


def _parse(raw):
    try:
        # Decode explicitly: accept the producer's UTF-8, not implicit UTF-16.
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_constant)
        json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
        return data
    except (UnicodeError, ValueError, RecursionError):
        raise SyncError('INVALID_JSON') from None


def _stamp(value):
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError('timezone required')
    except (TypeError, ValueError, OverflowError):
        raise SyncError('INVALID_FEED') from None


def _version(document):
    if not isinstance(document, dict):
        raise SyncError('INVALID_FEED')
    if type(document.get('schema_version')) is not int or document['schema_version'] != PUBLIC_SCHEMA_VERSION:
        raise SyncError('UNSUPPORTED_SCHEMA')


def validate_metadata(metadata):
    _version(metadata)
    if (set(metadata) != {'schema_version', 'generated_at', 'notice_count'}
            or type(metadata['notice_count']) is not int or metadata['notice_count'] < 0):
        raise SyncError('INVALID_FEED')
    _stamp(metadata['generated_at'])


def validate_pair(feed, metadata):
    """Validate M09 v1 fields without importing internal Notice/AI models."""
    validate_metadata(metadata)
    _version(feed)
    if set(feed) != {'schema_version', 'generated_at', 'notices'} or not isinstance(feed['notices'], list):
        raise SyncError('INVALID_FEED')
    _stamp(feed['generated_at'])
    if feed['generated_at'] != metadata['generated_at'] or len(feed['notices']) != metadata['notice_count']:
        raise SyncError('SNAPSHOT_MISMATCH')
    identities = set()
    dates = {'published_at', 'apply_start', 'apply_end'}
    for notice in feed['notices']:
        if not isinstance(notice, dict) or set(notice) != NOTICE_FIELDS:
            raise SyncError('INVALID_FEED')
        if type(notice['is_new']) is not bool:
            raise SyncError('INVALID_FEED')
        for field in NOTICE_FIELDS - dates - {'keywords', 'is_new'}:
            value = notice[field]
            if not isinstance(value, str) or (field != 'summary' and not value.strip()):
                raise SyncError('INVALID_FEED')
        if any(notice[field] is not None and not isinstance(notice[field], str) for field in dates):
            raise SyncError('INVALID_FEED')
        if not isinstance(notice['keywords'], list) or any(not isinstance(word, str) for word in notice['keywords']):
            raise SyncError('INVALID_FEED')
        if notice['notice_id'] in identities:
            raise SyncError('DUPLICATE_NOTICE_ID')
        identities.add(notice['notice_id'])


def download(url, timeout):
    """Bounded UTF-8 JSON response; no credentials or Gemini configuration."""
    request = Request(url, headers={'User-Agent': 'NoticeFeedClient/1.0', 'Accept': 'application/json'})
    with urlopen(request, timeout=timeout) as response:
        raw = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(raw) > MAX_DOWNLOAD_BYTES:
        raise SyncError('RESPONSE_TOO_LARGE')
    return raw


def _atomic_snapshot(path, snapshot):
    text = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n'
    text.encode('utf-8')
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                         dir=path.parent, prefix='.snapshot.', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError:
        raise SyncError('CACHE_WRITE_FAILED') from None
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def retained_snapshot(snapshot, *, today=None):
    """Project active v2 rows while preserving the producer snapshot on disk."""
    today = retention_date(today)
    notices = [n for n in snapshot['feed']['notices']
               if deadline_state(n['apply_end'], today=today, title=n['title'], content=n['summary']) != 'EXPIRED']
    if len(notices) == len(snapshot['feed']['notices']):
        return snapshot
    return {**snapshot, 'feed': {**snapshot['feed'], 'notices': notices},
            'metadata': {**snapshot['metadata'], 'notice_count': len(notices)}}


class FeedClient:
    """Single writer. Both public documents commit in one os.replace.

    transport(url, timeout) returns bytes and is injectable for offline tests.
    A cache is usable only after validation and for the same normalized base URL.
    """

    def __init__(self, base_url, *, cache_dir=None, timeout=30, transport=None, clock=None):
        try:
            parts = urlsplit(base_url)
            if (parts.scheme not in ('https', 'http') or not parts.hostname or parts.username is not None
                    or parts.password is not None or parts.query or parts.fragment
                    or any(ord(c) <= 32 or ord(c) == 127 for c in base_url)):
                raise ValueError('invalid URL')
            parts.port  # validate a malformed port before any request
            self.base_url = urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip('/') + '/', '', ''))
        except (TypeError, ValueError, AttributeError):
            raise SyncError('INVALID_BASE_URL') from None
        if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                or not math.isfinite(timeout) or timeout <= 0):
            raise SyncError('INVALID_TIMEOUT')
        self.timeout = timeout
        self.cache_path = Path(cache_dir if cache_dir is not None else DEFAULT_CACHE_DIR) / 'snapshot.json'
        self.transport = transport if transport is not None else download
        self.clock = clock

    def load_cache(self):
        try:
            snapshot = _parse(self.cache_path.read_bytes())
        except OSError:
            raise SyncError('CACHE_UNAVAILABLE') from None
        if (not isinstance(snapshot, dict) or set(snapshot) != {'base_url', 'feed', 'metadata'}
                or snapshot['base_url'] != self.base_url):
            raise SyncError('CACHE_SOURCE_MISMATCH')
        validate_pair(snapshot['feed'], snapshot['metadata'])
        retained = retained_snapshot(snapshot, today=self.clock() if self.clock else None)
        return retained

    def _fetch(self, filename):
        try:
            raw = self.transport(self.base_url + filename, self.timeout)
        except TimeoutError:
            raise SyncError('TIMEOUT') from None
        except URLError as error:
            raise SyncError('TIMEOUT' if isinstance(error.reason, TimeoutError) else 'NETWORK_ERROR') from None
        except (OSError, HTTPException):
            raise SyncError('NETWORK_ERROR') from None
        if not isinstance(raw, bytes):
            raise SyncError('INVALID_RESPONSE')
        if len(raw) > MAX_DOWNLOAD_BYTES:
            raise SyncError('RESPONSE_TOO_LARGE')
        return _parse(raw)

    def sync(self):
        try:
            cached = self.load_cache()
        except SyncError:
            cached = None
        try:
            metadata = self._fetch('metadata.json')
            validate_metadata(metadata)
            feed = self._fetch('notices.json')
            validate_pair(feed, metadata)
            snapshot = {'base_url': self.base_url, 'feed': feed, 'metadata': metadata}
            projection = retained_snapshot(snapshot, today=self.clock() if self.clock else None)
            status = 'UNCHANGED' if projection == cached else 'UPDATED'
            if status != 'UNCHANGED':
                _atomic_snapshot(self.cache_path, snapshot)  # Preserve validated producer pair.
            return SyncResult(status, projection['feed'], projection['metadata'])
        except SyncError as error:
            if cached is not None:
                return SyncResult('FALLBACK', cached['feed'], cached['metadata'], error.code)
            raise
