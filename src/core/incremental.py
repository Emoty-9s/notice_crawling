"""History-based crawling; dates bound refreshes, never admission of unknown IDs.

This state is private producer state. Notice/history remains authoritative when
recovering a missing, stale or damaged index. No local-client dependency.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from src.core.normalizer import normalize_whitespace
from src.core.storage import StorageError, _atomic_json, _read_json

BASELINE_DATE = date(2026, 11, 6)
KST = timezone(timedelta(hours=9))
VERSION = 1


class IncrementalError(ValueError):
    """Incremental-only failure: the affected source must use ordinary crawling."""


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timezone required')
    return parsed


def day(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value) if len(value) == 10 else timestamp(value).astimezone(KST).date()
    except (TypeError, ValueError):
        return None


def signature(item):
    # Tracking/paging URL parameters are deliberately not change signals.
    fields = {k:getattr(item,k,None) for k in
              ('title','published_at','apply_start','apply_end','institution','category')}
    fields = {k:normalize_whitespace(v) if isinstance(v,str) else v for k,v in fields.items()}
    return hashlib.sha256(json.dumps(fields,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def valid_source(value):
    if not isinstance(value,dict) or not isinstance(value.get('notices'),dict):
        raise IncrementalError('INVALID_SOURCE_INDEX')
    for field in ('baseline_at','last_successful_crawl_at'):
        if value.get(field) is not None:
            timestamp(value[field])
    for identity, record in value['notices'].items():
        if not isinstance(identity,str) or not identity or not isinstance(record,dict):
            raise IncrementalError('INVALID_NOTICE_INDEX')
        if record.get('published_at') is not None and day(record['published_at']) is None:
            raise IncrementalError('INVALID_PUBLISHED_DATE')
        if record.get('last_detail_checked_at') is not None:
            timestamp(record['last_detail_checked_at'])
    return value


class SourceCrawl:
    def __init__(self, scraper, history, state, now, *, fallback=None):
        self.scraper = scraper
        self.now = now
        self.stamp = now.astimezone(timezone.utc).isoformat().replace('+00:00','Z')
        self.today = now.astimezone(KST).date()
        self.window_start = self.today - timedelta(days=7)
        self.known = {n.notice_id:n for n in history if n.source_id == scraper.source_id}
        self.state = deepcopy(state)
        self.seen = {}
        self.checked = set()
        self.previous_date = None
        self.consecutive_known = 0
        self.order_usable = True
        self.early_stopped = False
        self.range_complete = True
        self.previous_range_incomplete = state.get('range_complete') is False
        self.enabled = self.today >= BASELINE_DATE
        self.metrics = dict(mode='INCREMENTAL' if self.enabled else 'PRE_BASELINE',
            baseline_date=BASELINE_DATE.isoformat(),window_start=self.window_start.isoformat(),
            window_end=self.today.isoformat(),list_pages=0,list_rows=0,listed_notices=0,
            detail_requests=0,detail_http_requests=0,list_http_requests=0,http_requests=0,
            detail_skipped=0,frozen_skipped=0,new_notices=0,recent_rechecked=0,
            early_stop=False,ordering='UNVERIFIED',fallback_reason=None,range_complete=True)
        options = scraper.config.get('incremental',{})
        try:
            if not isinstance(options,dict):
                raise IncrementalError('INVALID_INCREMENTAL_CONFIG')
            self.verified_order = options.get('latest_first_verified',False)
            self.refresh_limit = options.get('recent_refresh_limit',20)
            self.refresh_hours = options.get('recent_refresh_hours',6)
            self.page_limit = options.get('max_pages',100)
            self.stop_count = options.get('consecutive_known',10)
            if (type(self.verified_order) is not bool or
                any(type(v) is not int or not 0 <= v <= limit for v,limit in
                    ((self.refresh_limit,1000),(self.refresh_hours,168))) or
                type(self.page_limit) is not int or not 1 <= self.page_limit <= 100 or
                type(self.stop_count) is not int or not 1 <= self.stop_count <= 1000):
                raise IncrementalError('INVALID_INCREMENTAL_CONFIG')
            self.metrics['ordering'] = 'VERIFIED_LATEST_FIRST' if self.verified_order else 'UNVERIFIED'
            if fallback:
                self.disable(fallback)
        except Exception as error:
            self.verified_order = False
            self.disable(type(error).__name__)

    def disable(self, reason):
        self.enabled = False
        self.early_stopped = False
        self.metrics.update(mode='FULL_FALLBACK',fallback_reason=reason,early_stop=False,
                            detail_skipped=0,frozen_skipped=0,recent_rechecked=0,new_notices=0)
        self.scraper.logger.warning('incremental_fallback source_id=%s reason=%s',self.scraper.source_id,reason)

    def identity(self, item):
        value = self.scraper.notice_id_for(item)
        if not isinstance(value,str) or not value:
            raise IncrementalError('UNSUPPORTED_LIST_IDENTITY')
        return value

    def observe_page(self, items):
        self.metrics['list_pages'] += 1
        self.metrics['list_rows'] += len(items)
        if not self.enabled:
            return False
        identities = [self.identity(item) for item in items]
        self.seen.update(zip(identities,items))
        self.metrics['listed_notices'] = len(self.seen)
        if not self.verified_order:
            return False
        dates = [day(getattr(i,'published_at',None)) for i in items]
        if (not dates or any(d is None for d in dates) or
            any(a < b for a,b in zip(dates,dates[1:])) or
            (self.previous_date is not None and dates[0] > self.previous_date)):
            self.order_usable = False
            self.metrics['ordering'] = 'UNSTABLE_OR_MISSING_DATES'
            return False
        self.previous_date = dates[-1]
        for identity in identities:
            self.consecutive_known = self.consecutive_known + 1 if identity in self.known else 0
        # Inspect the WHOLE page first. A new ID after a known streak is never
        # discarded, even when its publication date is before the baseline.
        stop = (not self.previous_range_incomplete and self.order_usable and all(i in self.known for i in identities) and
                self.consecutive_known >= self.stop_count and dates[-1] < self.window_start)
        if stop:
            self.early_stopped = True
            self.metrics['early_stop'] = True
        return stop

    def may_fetch_page(self, count):
        limit = self.page_limit if self.enabled and self.verified_order and self.order_usable else self.scraper.max_pages
        if count < limit:
            return True
        if self.enabled and self.verified_order and self.order_usable:
            self.range_complete = False
            self.metrics['range_complete'] = False
        return False

    def frozen(self, old):
        acquired = day(old.first_seen_at)
        return acquired is not None and acquired < BASELINE_DATE

    def plan(self, items):
        if not self.enabled:
            self.metrics['listed_notices'] = len(items)
            return [(item,None) for item in items]
        unique = {}
        for item in items:
            key = self.identity(item)
            if key in unique and signature(unique[key]) != signature(item):
                raise IncrementalError('CONFLICTING_LIST_IDENTITY')
            unique.setdefault(key,item)
        self.seen.update(unique)
        self.metrics['listed_notices'] = len(unique)
        candidates = []
        for index,(identity,item) in enumerate(unique.items()):
            old = self.known.get(identity)
            if old is None or self.frozen(old):
                continue
            dates = [d for d in (day(getattr(item,'published_at',None)),day(old.published_at),day(old.first_seen_at)) if d is not None]
            if not dates or max(dates) < self.window_start:
                continue
            record = self.state['notices'].get(identity,{})
            changed = record.get('list_signature') != signature(item)
            checked = record.get('last_detail_checked_at')
            due = checked is None or timestamp(checked) <= self.now - timedelta(hours=self.refresh_hours)
            if changed or due:
                candidates.append((not changed,timestamp(checked).timestamp() if checked else float('-inf'),index,identity))
        # Rotate bounded refreshes by oldest check, rather than starving later
        # rows when the recent window contains more notices than the limit.
        selected = {row[-1] for row in sorted(candidates)[:self.refresh_limit]}
        result = []
        for identity,item in unique.items():
            old = self.known.get(identity)
            if old is None:
                self.metrics['new_notices'] += 1
                result.append((item,None))
            elif identity in selected:
                self.metrics['recent_rechecked'] += 1
                result.append((item,None))
            else:
                self.metrics['detail_skipped'] += 1
                self.metrics['frozen_skipped'] += int(self.frozen(old))
                result.append((item,old))
        return result

    def detail_succeeded(self, item, notice):
        if self.enabled and self.identity(item) != notice.notice_id:
            raise IncrementalError('NORMALIZED_IDENTITY_MISMATCH')
        self.checked.add(notice.notice_id)

    def request(self, phase):
        self.metrics['http_requests'] += 1
        self.metrics['detail_http_requests' if phase=='detail' else 'list_http_requests'] += 1

    def committed(self, notices):
        value = deepcopy(self.state)
        entries = value.setdefault('notices',{})
        for notice in [*self.known.values(),*notices]:
            record = entries.setdefault(notice.notice_id,{})
            record.update(published_at=notice.published_at,url=notice.url)
            if notice.notice_id in self.checked:
                record['last_detail_checked_at'] = self.stamp
            if notice.notice_id in self.seen:
                record['list_signature'] = signature(self.seen[notice.notice_id])
                record['last_list_seen_at'] = self.stamp
        if self.range_complete:
            old = value.get('last_successful_crawl_at')
            if old is None or timestamp(old) <= self.now:
                value['last_successful_crawl_at'] = self.stamp
            value['baseline_at'] = value.get('baseline_at') or (
                datetime.combine(BASELINE_DATE,datetime.min.time(),KST).isoformat()
                if any(self.frozen(n) for n in self.known.values()) else
                min((n.first_seen_at for n in self.known.values()),default=self.stamp))
        value['last_attempt_at'] = self.stamp
        value['range_complete'] = self.range_complete
        return value


class IncrementalCrawl:
    def __init__(self, data_dir, history, statuses, now):
        self.path = Path(data_dir)/'crawl_state.json'
        self.history, self.statuses, self.now = history,statuses,now
        self.active = now.astimezone(KST).date() >= BASELINE_DATE
        self.sessions = {}
        self.load_error = None
        self.document = dict(version=VERSION,initial_baseline_date=BASELINE_DATE.isoformat(),sources={})
        try:
            value = _read_json(self.path,None)
            if value is not None:
                if (not isinstance(value,dict) or type(value.get('version')) is not int or value.get('version') != VERSION or
                    value.get('initial_baseline_date') != BASELINE_DATE.isoformat() or not isinstance(value.get('sources'),dict)):
                    raise IncrementalError('INVALID_CRAWL_STATE')
                self.document = value
        except (StorageError,ValueError,TypeError):
            self.load_error = 'INVALID_CRAWL_STATE'
        self.recovery_needed = bool(self.load_error)

    def for_source(self, scraper):
        source = scraper.source_id
        fallback = self.load_error
        value = self.document['sources'].get(source)
        if value is not None:
            try:
                value = valid_source(value)
            except (ValueError,TypeError,KeyError,AttributeError):
                fallback = 'INVALID_SOURCE_INDEX'
                self.recovery_needed = True
                value = None
        if value is None:
            legacy = self.statuses.get(source,{}).get('last_success_at')
            try:
                if legacy is not None:
                    timestamp(legacy)
            except (ValueError,TypeError,AttributeError):
                legacy = None
                fallback = 'INVALID_LEGACY_CURSOR'
            value = dict(baseline_at=None,last_successful_crawl_at=legacy,notices={})
        session = SourceCrawl(scraper,self.history,value,self.now,fallback=fallback)
        self.sessions[source] = session
        return session

    def commit(self, results):
        if not self.active:
            return
        if self.recovery_needed and self.path.exists():
            raw = self.path.read_bytes()
            backup = self.path.parent/'crawl_state_recovery'/f'{hashlib.sha256(raw).hexdigest()}.json'
            backup.parent.mkdir(parents=True,exist_ok=True)
            if not backup.exists():
                backup.write_bytes(raw)
        for source,session in self.sessions.items():
            if source in results:
                self.document['sources'][source] = session.committed(results[source])
        _atomic_json(self.path,self.document)

    def diagnostics(self):
        result = {}
        for source,session in self.sessions.items():
            value = self.document['sources'].get(source,session.state)
            try:
                value = valid_source(value)
            except (ValueError,TypeError,AttributeError,KeyError):
                value = session.state
            result[source] = {**session.metrics,'last_successful_crawl_at':value.get('last_successful_crawl_at')}
        return result
