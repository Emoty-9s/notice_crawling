"""M10 central orchestration; all network/clock/storage dependencies injectable."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from src.ai.work_queue import BatchSession, RunLimits, utcnow, queue_statistics
from src.ai.prefilter import Prefilter
from src.core.state_lock import state_writer
from src.core.storage import _atomic_json
from src.core.diff import compare_batch
from src.core.models import Notice, NoticeStatus
from src.core.storage import JsonStorage
from src.renderer.feed import PUBLIC_DIR, build_feed, write_feed
from src.scrapers.registry import build_mvp_registry, build_registry


CONFIG_PATH = Path(__file__).resolve().parents[1] / 'config' / 'sites.yaml'
MVP_SOURCES = frozenset({'khidi_business', 'kised_bid_public', 'rda_bid', 'seoul_rnd_notice', 'kipa_bid'})
SUPPORTED_SOURCES = MVP_SOURCES | {'ripc_pms', 'kista_ippro'}
ANALYSIS_MAX_CALLS_PER_RUN = RunLimits().max_api_requests_per_run  # legacy name: HTTP requests, including retries


class PipelineConfigError(ValueError):
    """Safe configuration error, with no secret/config values in the message."""


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def _bad_constant(value):
    raise ValueError('nonstandard JSON constant')


def load_site_configs(path: str | Path = CONFIG_PATH) -> list[dict]:
    """Read the project's JSON-syntax YAML 1.2 without adding dependencies."""
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'),
                          object_pairs_hook=_unique_pairs, parse_constant=_bad_constant)
        sites = data['sites']
        if not isinstance(sites, list):
            raise ValueError('sites must be an array')
        seen = set()
        for site in sites:
            source = site['source_id']
            if not isinstance(source, str) or not source.strip() or source in seen:
                raise ValueError('invalid/duplicate source')
            if type(site.get('enabled', False)) is not bool:
                raise ValueError('invalid enabled flag')
            if site.get('enabled', False) and source not in SUPPORTED_SOURCES:
                raise ValueError('enabled source has no implemented adapter')
            seen.add(source)
        if not MVP_SOURCES <= seen:
            raise ValueError('missing MVP configuration')
        return sites
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, RecursionError):
        raise PipelineConfigError('INVALID_SITE_CONFIG: check JSON-syntax sites.yaml and supported enabled sources') from None


@dataclass(frozen=True)
class PipelineResult:
    notices: tuple[Notice, ...]
    observed: tuple[Notice, ...]
    scraper_failures: tuple[str, ...]
    analysis_failures: tuple[str, ...]
    skipped: tuple[str, ...]
    feed_count: int
    analysis_incomplete: bool = False

    @property
    def degraded(self) -> bool:
        return bool(self.scraper_failures or self.analysis_failures or self.analysis_incomplete)


def run_pipeline(
    *, client, config_path=CONFIG_PATH, storage=None, public_dir=None,
    clock=None, transport_factory=None, logger=None, analysis_max_calls=None, analysis_limits=None,
) -> PipelineResult:
    # Validate config/state before acquiring the OS lock; validate again inside
    # the locked run so no stale pre-lock state is used for work selection.
    load_site_configs(config_path)
    store = storage if storage is not None else JsonStorage()
    store.load_notices();store.load_scraper_status()
    public_root = Path(public_dir) if public_dir is not None else PUBLIC_DIR
    protected = {store.notices_path.resolve(),store.scraper_status_path.resolve()}
    if any((public_root/name).resolve() in protected for name in ('notices.json','metadata.json')):
        raise PipelineConfigError('OUTPUT_PATH_COLLISION: public feed must not overwrite storage files')
    with state_writer(store.data_dir):
        return _run_pipeline(client=client,config_path=config_path,storage=store,public_dir=public_dir,
            clock=clock,transport_factory=transport_factory,logger=logger,
            analysis_max_calls=analysis_max_calls,analysis_limits=analysis_limits)


def _run_pipeline(
    *, client, config_path=CONFIG_PATH, storage=None, public_dir=None,
    clock=None, transport_factory=None, logger=None, analysis_max_calls=None, analysis_limits=None,
) -> PipelineResult:
    """One central run. Preserved history and bounded enabled-source backlog.

    Scrapers already normalize through M04/M05 and M03, so do not regenerate
    identity or normalize a second time here. A fresh analyzer scopes attempts
    to this run; persisted success handles cross-run cache reuse.
    """
    configs = load_site_configs(config_path)
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise PipelineConfigError('INVALID_CLOCK: timezone-aware datetime required')
    stamp = now.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    limits = analysis_limits or RunLimits.from_env()
    if analysis_max_calls is not None:
        limits = replace(limits,max_api_requests_per_run=analysis_max_calls)
    prefilter = Prefilter()  # Fail bad policy configuration before any collection.
    store = storage if storage is not None else JsonStorage()
    public_root = Path(public_dir) if public_dir is not None else PUBLIC_DIR
    protected = {store.notices_path.resolve(), store.scraper_status_path.resolve()}
    if any((public_root / name).resolve() in protected for name in ('notices.json', 'metadata.json')):
        raise PipelineConfigError('OUTPUT_PATH_COLLISION: public feed must not overwrite storage files')
    # Validate local state before any external request; never reset bad data.
    previous = store.load_notices()
    statuses = store.load_scraper_status()
    compare_batch([], previous, observed_at=stamp)
    builder = build_registry if any(config.get('enabled', False) and config['source_id'] in
                                   SUPPORTED_SOURCES - MVP_SOURCES for config in configs) else build_mvp_registry
    registry = builder(configs, transport_factory=transport_factory,
                                  clock=lambda: now, logger=logger)
    collected = registry.run()  # fetch/parse/normalize, with source isolation
    compared = compare_batch(collected, previous, observed_at=stamp)
    # Always retain complete observation history, including expired records.
    # Clear last run's transient lifecycle status even when a source fails.
    current_notices = compared.notices
    merged = {n.notice_id: replace(n, status=NoticeStatus.EXISTING) for n in previous}
    merged.update({n.notice_id: n for n in current_notices})
    enabled = {c['source_id'] for c in configs if c.get('enabled', False)}
    for source, records in registry.results.items():
        statuses[source] = {
            'status': 'SUCCESS', 'last_attempt_at': stamp, 'last_success_at': stamp,
            'notices_found': len({notice.notice_id for notice in records}),
            'error_type': None, 'error_message': None,
        }
    for source, failure in registry.errors.items():
        statuses[source] = {
            'status': 'ERROR', 'last_attempt_at': stamp,
            'last_success_at': statuses.get(source, {}).get('last_success_at'),
            'notices_found': 0, 'error_type': failure.error_type,
            'error_message': f'Scraper failed during {failure.stage}',
        }
    for source in registry.skipped:
        old = statuses.get(source, {})
        statuses[source] = {
            'status': 'WARNING', 'last_attempt_at': old.get('last_attempt_at'),
            'last_success_at': old.get('last_success_at'), 'notices_found': old.get('notices_found'),
            'error_type': 'DISABLED', 'error_message': 'Scraper disabled; no attempt made',
        }

    # Preserve collection first; one atomic Notice snapshot contains history,
    # queue and decisions. Checkpoint before calls and after each accepted result.
    store.save_notices(sorted(merged.values(),key=lambda n:(n.source_id,n.notice_id)))
    store.save_scraper_status(statuses)
    analyzer = BatchSession(client,limits=limits,clock=clock or utcnow,prefilter=prefilter)
    def checkpoint(records):
        store.save_notices(sorted(records,key=lambda n:(n.source_id,n.notice_id)))
        _atomic_json(store.data_dir/'analysis_diagnostics.json',dict(
            metrics_phase='CHECKPOINT',collection_status='PARTIAL' if registry.errors else 'SUCCESS',
            prefilter_status='SUCCESS',publication_status='PENDING',**queue_statistics(records,now),gemini=analyzer.metrics))
    snapshot = analyzer.run(list(merged.values()),enabled,checkpoint)
    snapshot.sort(key=lambda n:(n.source_id,n.notice_id))
    merged = {n.notice_id:n for n in snapshot}
    observed = [merged[n.notice_id] for n in current_notices]
    feed = build_feed(snapshot,generated_at=stamp)
    try:
        write_feed(snapshot, generated_at=stamp, output_dir=public_dir)
    except Exception:
        # A failed feed write must not discard this run's scraper health record.
        store.save_scraper_status(statuses)
        raise
    store.save_scraper_status(statuses)
    _atomic_json(store.data_dir/'analysis_diagnostics.json',dict(
        metrics_phase='FINAL',collection_status='PARTIAL' if registry.errors else 'SUCCESS',
        prefilter_status='SUCCESS',publication_status='SUCCESS',**queue_statistics(snapshot,now),gemini=analyzer.metrics))
    return PipelineResult(tuple(snapshot), tuple(observed), tuple(sorted(registry.errors)),
                          tuple(sorted(analyzer.errors)), tuple(registry.skipped), len(feed['notices']),
                          queue_statistics(snapshot,now)['analysis_status'] != 'SUCCESS')
