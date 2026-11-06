"""M10 central orchestration; all network/clock/storage dependencies injectable."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

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
ANALYSIS_MAX_CALLS_PER_RUN = 0  # retired compatibility constant; never invokes AI


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
    *, client=None, config_path=CONFIG_PATH, storage=None, public_dir=None,
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
    *, client=None, config_path=CONFIG_PATH, storage=None, public_dir=None,
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
    from src.core.extraction import Extractor, ExtractionQueue, Resource
    extractor = Extractor(store.data_dir / 'ocr_cache', isolated=True)
    queue = ExtractionQueue()
    registry.set_extractor(queue)
    collected = registry.run()  # fetch/parse/normalize, with source isolation
    compare_batch(collected, previous, observed_at=stamp) # reject conflicting identities before scheduling
    previous_by_id = {n.notice_id:n for n in previous}
    def extraction_priority(n):
        old = previous_by_id.get(n.notice_id)
        if old is None or (old.extraction.get('original_hash', old.content_hash) != n.content_hash):
            return 0
        return 1 if old.extraction.get('status') != 'SUCCESS' else 2
    # Work from all sources before filtering. Round robin within priority tiers
    # prevents a large first source from starving other agencies every day.
    from itertools import zip_longest
    ordered = []
    for priority in range(3):
        groups = [[n for n in collected if n.source_id == source and extraction_priority(n)==priority]
                  for source in dict.fromkeys(n.source_id for n in collected)]
        ordered.extend(n for row in zip_longest(*groups) for n in row if n is not None)
    processed = {}
    for notice in ordered:
        if notice.notice_id in queue.resources:
            notice = extractor.enrich(notice, queue.resources[notice.notice_id])
        processed[notice.notice_id] = notice
    collected = [processed[n.notice_id] for n in collected]
    compared = compare_batch(collected, previous, observed_at=stamp)
    # Always retain complete observation history, including expired records.
    # Clear last run's transient lifecycle status even when a source fails.
    current_notices = compared.notices
    merged = {n.notice_id: replace(n, status=NoticeStatus.EXISTING) for n in previous}
    merged.update({n.notice_id: n for n in current_notices})
    enabled = {c['source_id'] for c in configs if c.get('enabled', False)}
    observed_ids = {n.notice_id for n in current_notices}
    for old in previous:
        if (old.source_id not in enabled or old.notice_id in observed_ids or not old.extraction
                or old.extraction.get('status') == 'SUCCESS'):
            continue
        resources = [Resource(r['source_url'],r.get('name',''),r.get('kind','attachment'))
                     for r in old.extraction.get('resources',[]) if r.get('source_url')]
        if resources:
            retry = extractor.enrich(replace(old,content_text=old.extraction.get('original_text',''),
                                            content_hash=old.extraction.get('original_hash',old.content_hash)),resources)
            merged[old.notice_id] = replace(retry,status=NoticeStatus.EXISTING,
                updated_at=stamp if retry.content_hash != old.content_hash else old.updated_at)
    _atomic_json(store.data_dir / 'ocr_diagnostics.json', extractor.metrics)
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
    # Historical Gemini results and queue fields remain untouched. Only update
    # the deterministic prefilter metadata; no provider or local model here.
    snapshot = [prefilter.evaluate(n,stamp) for n in merged.values()]
    store.save_notices(sorted(snapshot,key=lambda n:(n.source_id,n.notice_id)))
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
        prefilter_status='SUCCESS',publication_status='SUCCESS',analysis_status='LOCAL_ONLY',
        extraction_status='PARTIAL' if any(n.extraction.get('status') in {'PARTIAL','FAILED'} for n in snapshot) else 'SUCCESS',
        total_history=len(snapshot),public_eligible=len(feed['notices']),external_ai_calls=0,
        prefilter_counts={s:sum(n.analysis.prefilter_status==s for n in snapshot)
                          for s in ('CANDIDATE','REVIEW','CLEARLY_UNRELATED')}))
    return PipelineResult(tuple(snapshot), tuple(observed), tuple(sorted(registry.errors)),
                          (), tuple(registry.skipped), len(feed['notices']),
                          any(n.extraction.get('status') in {'PARTIAL','FAILED'} for n in snapshot))
