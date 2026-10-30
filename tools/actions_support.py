"""M11 offline-testable CI preflight, publication checks and safe diagnostics.

No network calls, credentials on disk, or changes to M00-M10 contracts.
Run from the repository root: python -m tools.actions_support --help.
"""

import argparse
import json
import os
import re
from pathlib import Path

from src.core.diff import compare_batch
from src.core.storage import JsonStorage, _atomic_json, _read_json
from src.pipeline import CONFIG_PATH, load_site_configs
from src.renderer.feed import build_feed


class ActionsCheckError(ValueError):
    """Fixed safe message; do not expose arbitrary API/environment values."""


def preflight(config_path=CONFIG_PATH, *, environ=None):
    env = os.environ if environ is None else environ
    sites = load_site_configs(config_path)
    count = sum(site.get('enabled', False) for site in sites)
    if not count:
        raise ActionsCheckError('NO_ENABLED_SITES: enable at least one implemented source')
    key, model = env.get('GEMINI_API_KEY', ''), env.get('GEMINI_MODEL', '')
    if not key.strip() or any(ord(c) < 32 or ord(c) == 127 for c in key):
        raise ActionsCheckError('INVALID_GEMINI_KEY: configure the GEMINI_API_KEY Actions secret')
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]*', model):
        raise ActionsCheckError('INVALID_GEMINI_MODEL: configure the GEMINI_MODEL Actions variable')
    return {'enabled_sites': count, 'configuration': 'READY'}


def validate_state(data_dir):
    store = JsonStorage(data_dir)
    for path in (store.notices_path, store.scraper_status_path):
        if not path.is_file() or path.is_symlink():
            raise ActionsCheckError('INCOMPLETE_STATE: both state JSON files are required')
    notices, statuses = store.load_notices(), store.load_scraper_status()
    compare_batch([], notices, observed_at='2000-01-01T00:00:00Z')
    return notices, statuses


def stage_public(data_dir, public_dir, stage_dir):
    """Validate feed against the saved snapshot; copy only the two public files."""
    notices, _ = validate_state(data_dir)
    public = Path(public_dir)
    for name in ('notices.json', 'metadata.json'):
        if not (public/name).is_file() or (public/name).is_symlink():
            raise ActionsCheckError('INCOMPLETE_FEED: both public JSON files are required')
    feed = _read_json(public/'notices.json', None)
    metadata = _read_json(public/'metadata.json', None)
    if not isinstance(feed, dict) or not isinstance(metadata, dict):
        raise ActionsCheckError('INVALID_FEED: expected two JSON objects')
    expected = build_feed(notices, generated_at=feed.get('generated_at'))
    expected_metadata = {'schema_version': 1, 'generated_at': expected['generated_at'],
                         'notice_count': len(expected['notices'])}
    # JSON equality also compares number/bool as equal: explicitly retain schema/count types.
    if (feed != expected or metadata != expected_metadata
        or type(feed.get('schema_version')) is not int
        or type(metadata.get('schema_version')) is not int
        or type(metadata.get('notice_count')) is not int):
        raise ActionsCheckError('FEED_SNAPSHOT_MISMATCH: refuse stale or inconsistent publication')
    target = Path(stage_dir)
    if target.exists():
        raise ActionsCheckError('STAGE_EXISTS: use a fresh empty publication path')
    target.mkdir(parents=True)
    _atomic_json(target/'notices.json', expected)
    _atomic_json(target/'metadata.json', expected_metadata)
    return expected_metadata


def diagnostics(data_dir):
    """No body/title/reason/raw error, environment values or secret in output."""
    try:
        notices, statuses = validate_state(data_dir)
    except Exception:
        return {'state': 'MISSING_OR_INVALID', 'hint': 'Inspect the first failed Actions step; state was not reset'}
    return {
        'state': 'VALID', 'stored_notices': len(notices),
        'scrapers': {source: {'status': status['status'], 'notices_found': status.get('notices_found')}
                     for source, status in sorted(statuses.items())},
        'analysis_counts': {status: sum(notice.gemini.status.value == status for notice in notices)
                            for status in ('NOT_ANALYZED', 'SUCCESS', 'FAILED', 'PENDING')},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description='M11 Actions publication checks (no network).')
    parser.add_argument('command', choices=('preflight', 'validate-state', 'stage', 'diagnostics'))
    parser.add_argument('--config', default=CONFIG_PATH)
    parser.add_argument('--data-dir', default='.run/data')
    parser.add_argument('--public-dir', default='.run/public')
    parser.add_argument('--stage-dir', default='.run/pages')
    args = parser.parse_args(argv)
    try:
        if args.command == 'preflight':
            report = preflight(args.config)
        elif args.command == 'validate-state':
            notices, _ = validate_state(args.data_dir)
            report = {'state': 'VALID', 'stored_notices': len(notices)}
        elif args.command == 'stage':
            report = stage_public(args.data_dir, args.public_dir, args.stage_dir)
        else:
            report = diagnostics(args.data_dir)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as error:
        if isinstance(error, ActionsCheckError):
            print(f'::error::{error}')
        else:
            print(f'::error::ACTIONS_CHECK_FAILED ({type(error).__name__}): inspect config/state/feed schema; no files were reset')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
