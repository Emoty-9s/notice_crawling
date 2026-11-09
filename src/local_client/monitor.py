"""Dashboard I/O and presentation state. No Tk, scraper, Gemini or DB writes."""
import copy
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from http.client import HTTPException

from .dashboard import DashboardData, DashboardError, _load_performances
from .sync import FeedClient, SyncError, download, _parse, _atomic_snapshot
from src.renderer.source_status import SOURCES, validate_source_status, timestamp
from .seen import seen_path
from .notice_settings import settings_path
from src.core.eligibility import deadline_date

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
    if Path(database_path).resolve() in (Path(cache_path).resolve(), seen_path(cache_path).resolve(), settings_path(cache_path).resolve(),
                                       Path(str(cache_path) + '.sources.json').resolve(),
                                       Path(str(cache_path)+'.work.json').resolve(),
                                       Path(str(cache_path)+'.technical.json').resolve()):
        return None
    try:
        client = FeedClient(base_url)
        client.cache_path = Path(cache_path)
        snapshot = client.load_cache()
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
    if Path(database_path).resolve() in (cache, cache.with_name(cache.name + '.sources.json'), seen_path(cache).resolve(), settings_path(cache).resolve(),
                                       Path(str(cache)+'.work.json'),Path(str(cache)+'.technical.json')):
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


def notice_badge(notice, seen=None, *, generated_at=None):
    # Local acknowledgement never changes a central-run discovery badge.
    return 'NEW' if notice.get('is_new') is True else 'EXISTING'


def ordered_notices(notices, seen=None, *, generated_at=None):
    rows = copy.deepcopy(notices)
    rows.sort(key=lambda row: (notice_badge(row, generated_at=generated_at) != 'NEW',
                              deadline_date(row['apply_end']) or date.max,
                              row['source_id'], row['notice_id']))
    return rows


SOURCE_LIST_URLS = {
    'khidi_business': 'https://www.khidi.or.kr/board?menuId=MENU01108',
    'kised_bid_public': 'https://www.kised.or.kr/board.es?bid=0005&mid=a10303000000',
    'rda_bid': 'https://www.rda.go.kr/board/board.do?mode=list&prgId=bid_bidancmEntry',
    'seoul_rnd_notice': 'https://seoul.rnbd.kr/client/c030200/c030200_00.jsp',
    'kipa_bid': 'https://www.kipa.org/kipa/notice/kw_0402.jsp',
    'kista_ippro': 'https://biz.kista.re.kr/ippro//com/iprndMain/selectBusinessAnnounceList.do?bbsType=ac',
    'tipa_legacy_bid': 'https://www.tipa.or.kr/s040305',
    'kiat_home': 'https://cont.kiat.or.kr/bidding/biddingList.do',
    'ripc_pms': 'https://pms.ripc.org/pms/biz/partner/tenderNotice/list.do',
}


def source_list_url(source):
    url = SOURCE_LIST_URLS.get(source)
    return url if url and safe_original_url(url) else None


def safe_original_url(url):
    try:
        parts = urlsplit(url)
        return (parts.scheme in ('http', 'https') and bool(parts.hostname)
                and parts.username is None and parts.password is None
                and not any(ord(c) < 33 for c in url))
    except (TypeError, ValueError):
        return False
