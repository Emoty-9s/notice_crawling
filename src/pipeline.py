"""M10 central orchestration; all network/clock/storage dependencies injectable."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from src.ai.relevance import RelevanceAnalyzer
from src.ai.gemini import GeminiClient
from src.core.diff import compare_batch
from src.core.models import Notice, GeminiStatus, NoticeStatus
from src.core.storage import JsonStorage
from src.core.eligibility import deadline_state, current_analysis
from src.renderer.feed import PUBLIC_DIR, build_feed, write_feed
from src.scrapers.registry import build_mvp_registry, build_registry


CONFIG_PATH = Path(__file__).resolve().parents[1] / 'config' / 'sites.yaml'
MVP_SOURCES = frozenset({'khidi_business', 'kised_bid_public', 'rda_bid', 'seoul_rnd_notice', 'kipa_bid'})
SUPPORTED_SOURCES = MVP_SOURCES | {'ripc_pms', 'kista_ippro'}
ANALYSIS_MAX_CALLS_PER_RUN = 60


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

    @property
    def degraded(self) -> bool:
        return bool(self.scraper_failures or self.analysis_failures)


def run_pipeline(
    *, client, config_path=CONFIG_PATH, storage=None, public_dir=None,
    clock=None, transport_factory=None, logger=None, analysis_max_calls=ANALYSIS_MAX_CALLS_PER_RUN,
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
    analyzer = RelevanceAnalyzer(client, clock=lambda: now, logger=logger,
                                 retry_existing=True, max_calls=analysis_max_calls,
                                 stop_on_rate_limit=True,
                                 min_call_interval=6 if isinstance(client, GeminiClient) else 0)
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
    queue = [n for n in merged.values() if n.source_id in enabled and not current_analysis(n)
             and deadline_state(n.apply_end, today=now, title=n.title, content=n.content_text) != 'EXPIRED']
    queue.sort(key=lambda n: ({NoticeStatus.NEW: 0, NoticeStatus.UPDATED: 1}.get(n.status,
                              2 if deadline_state(n.apply_end, today=now) == 'ACTIVE' else 3),
                              n.first_seen_at, n.notice_id))
    analyzed = {n.notice_id: n for n in analyzer.analyze_batch(queue)}
    merged.update(analyzed)
    observed = [merged[n.notice_id] for n in current_notices]
    snapshot = sorted(merged.values(), key=lambda notice: (notice.source_id, notice.notice_id))
    # Validate the complete public projection before committing the new storage.
    feed = build_feed(snapshot, generated_at=stamp)

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

    store.save_notices(snapshot)
    try:
        write_feed(snapshot, generated_at=stamp, output_dir=public_dir)
    except Exception:
        # A failed feed write must not discard this run's scraper health record.
        store.save_scraper_status(statuses)
        raise
    store.save_scraper_status(statuses)
    return PipelineResult(tuple(snapshot), tuple(observed), tuple(sorted(registry.errors)),
                          tuple(sorted(analyzer.errors)), tuple(registry.skipped), len(feed['notices']))
