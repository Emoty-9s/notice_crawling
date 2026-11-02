"""Dashboard I/O and presentation state. No Tk, scraper, Gemini or DB writes."""
import copy
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from http.client import HTTPException

from .dashboard import DashboardData, DashboardError, _load_cache, _load_performances
from .sync import FeedClient, SyncError, download, _parse, _atomic_snapshot
from src.renderer.source_status import SOURCES, validate_source_status, timestamp

DEFAULT_FEED_URL = 'https://emoty-9s.github.io/notice_crawling/'


@dataclass(frozen=True)
class MonitorResult:
    connection: str
    data: DashboardData | None
    database_error: bool = False
    sources: dict | None = None
    sources_cached: bool = False
    checked_at: str | None = None
    error_code: str | None = None


def read_local(cache_path, database_path, base_url):
    try:
        snapshot = _load_cache(cache_path)
        if snapshot['base_url'] != FeedClient(base_url).base_url:
            return None
    except (DashboardError, SyncError):
        return None
    records, error = read_database(database_path)
    return MonitorResult('FALLBACK', DashboardData(snapshot, records), database_error=error)


def read_database(path):
    try:
        return _load_performances(path), False
    except DashboardError:
        return (), True


def sync_monitor(base_url, cache_path, database_path, *, transport=None):
    cache = Path(cache_path).resolve()
    if Path(database_path).resolve() in (cache, cache.with_name(cache.name + '.sources.json')):
        return MonitorResult('ERROR', None, error_code='PATH_COLLISION')
    client = FeedClient(base_url, cache_dir=Path(cache_path).parent, timeout=15, transport=transport)
    client.cache_path = Path(cache_path)  # Preserve an explicit arbitrary cache filename.
    try:
        result = client.sync()
    except SyncError as error:
        return MonitorResult('ERROR', None, error_code=error.code)
    records, db_error = read_database(database_path)
    snapshot = dict(base_url=client.base_url, feed=result.feed, metadata=result.metadata)
    checked = datetime.now(timezone.utc).isoformat() if result.status != 'FALLBACK' else None
    return MonitorResult(result.status, DashboardData(snapshot, records), database_error=db_error,
                         checked_at=checked, error_code=result.error_code)


def read_sources(base_url, cache_path, *, transport=None):
    """Optional health document; an unavailable endpoint never breaks the feed.

    Sidecar caches only the validated public projection, bound to its origin.
    Cached health is explicitly marked stale by the caller.
    """
    base = FeedClient(base_url).base_url
    path = Path(cache_path).with_name(Path(cache_path).name + '.sources.json')
    try:
        raw = (transport or download)(base + 'source_status.json', 10)
        if not isinstance(raw, bytes) or len(raw) > 65536:
            raise ValueError('INVALID_SOURCE_STATUS')
        document = validate_source_status(_parse(raw))
        try:
            _atomic_snapshot(path, {'base_url': base, 'document': document})
        except SyncError:
            pass  # Health cache storage must not turn online success into failure.
        return document, False
    except (OSError, ValueError, TypeError, SyncError, HTTPException):
        try:
            cached = _parse(path.read_bytes())
            if set(cached) != {'base_url', 'document'} or cached['base_url'] != base:
                raise ValueError('SOURCE_MISMATCH')
            return validate_source_status(cached['document']), True
        except (OSError, ValueError, TypeError, SyncError):
            return None, False


def notice_badge(notice, baseline):
    old = baseline.get(notice['notice_id'])
    if old is None:
        return 'NEW'
    return 'UPDATED' if old != notice['updated_at'] else 'EXISTING'


def ordered_notices(notices, baseline):
    rows = copy.deepcopy(notices)
    rows.sort(key=lambda row: timestamp(row['updated_at']), reverse=True)
    rows.sort(key=lambda row: {'NEW': 0, 'UPDATED': 1, 'EXISTING': 2}[notice_badge(row, baseline)])
    return rows


def safe_original_url(url):
    try:
        parts = urlsplit(url)
        return (parts.scheme in ('http', 'https') and bool(parts.hostname)
                and parts.username is None and parts.password is None
                and not any(ord(c) < 33 for c in url))
    except (TypeError, ValueError):
        return False
