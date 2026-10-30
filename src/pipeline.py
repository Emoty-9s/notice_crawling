"""M10 central orchestration; all network/clock/storage dependencies injectable."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.ai.relevance import RelevanceAnalyzer
from src.core.diff import compare_batch
from src.core.models import Notice
from src.core.storage import JsonStorage
from src.renderer.feed import PUBLIC_DIR, build_feed, write_feed
from src.scrapers.registry import build_mvp_registry


CONFIG_PATH = Path(__file__).resolve().parents[1] / 'config' / 'sites.yaml'
MVP_SOURCES = frozenset({'khidi_business', 'kised_bid_public', 'rda_bid', 'seoul_rnd_notice', 'kipa_bid'})


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
            if site.get('enabled', False) and source not in MVP_SOURCES:
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
    clock=None, transport_factory=None, logger=None,
) -> PipelineResult:
    """One central run. No implicit deletion or retry of unobserved records.

    Scrapers already normalize through M04/M05 and M03, so do not regenerate
    identity or normalize a second time here. A fresh analyzer scopes attempts
    to this run; persisted success handles cross-run cache reuse.
    """
    configs = load_site_configs(config_path)
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise PipelineConfigError('INVALID_CLOCK: timezone-aware datetime required')
    stamp = now.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    store = storage if storage is not None else JsonStorage()
    public_root = Path(public_dir) if public_dir is not None else PUBLIC_DIR
    protected = {store.notices_path.resolve(), store.scraper_status_path.resolve()}
    if any((public_root / name).resolve() in protected for name in ('notices.json', 'metadata.json')):
        raise PipelineConfigError('OUTPUT_PATH_COLLISION: public feed must not overwrite storage files')
    # Validate local state before any external request; never reset bad data.
    previous = store.load_notices()
    statuses = store.load_scraper_status()
    compare_batch([], previous, observed_at=stamp)
    registry = build_mvp_registry(configs, transport_factory=transport_factory,
                                  clock=lambda: now, logger=logger)
    collected = registry.run()  # fetch/parse/normalize, with source isolation
    compared = compare_batch(collected, previous, observed_at=stamp)
    analyzer = RelevanceAnalyzer(client, clock=lambda: now, logger=logger)
    observed = analyzer.analyze_batch(compared.notices)
    merged = {notice.notice_id: notice for notice in previous}
    merged.update((notice.notice_id, notice) for notice in observed)
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
