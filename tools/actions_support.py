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
from src.renderer.source_status import public_source_status


class ActionsCheckError(ValueError):
    """Fixed safe message; do not expose arbitrary API/environment values."""


PUBLIC_INDEX = '''<!doctype html>
<html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Notice Crawling · 공개 공고 feed</title>
<style>body{background:#0c0f14;color:#e8edf5;font:17px/1.7 system-ui;
max-width:760px;margin:10vh auto;padding:24px}a{color:#8db9ff}</style>
<h1>공개 공고 feed</h1>
<p>사전 필터를 통과한 유효 공고입니다. 지원 가능성과 참가 자격은 Windows 앱에서 확인하세요.</p>
<p>schema v3는 최신 Windows 앱이 필요합니다. 이전 v2 앱은 업데이트해 주세요.</p>
<ul><li><a href="notices.json">공고 목록 · schema v3</a></li>
<li><a href="metadata.json">생성 시각 및 공고 수</a></li>
<li><a href="source_status.json">7개 기관 수집 상태</a></li></ul>
<p>실적 업로드와 실적 관리는 Windows 앱의 로컬 DB에서 처리합니다.</p>
</html>
'''


def preflight(config_path=CONFIG_PATH, *, environ=None):
    env = os.environ if environ is None else environ
    sites = load_site_configs(config_path)
    count = sum(site.get('enabled', False) for site in sites)
    if not count:
        raise ActionsCheckError('NO_ENABLED_SITES: enable at least one implemented source')
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
    """Publish the unchanged feed pair plus an explicit minimal health projection."""
    notices, statuses = validate_state(data_dir)
    public = Path(public_dir)
    for name in ('notices.json', 'metadata.json'):
        if not (public/name).is_file() or (public/name).is_symlink():
            raise ActionsCheckError('INCOMPLETE_FEED: both public JSON files are required')
    feed = _read_json(public/'notices.json', None)
    metadata = _read_json(public/'metadata.json', None)
    if not isinstance(feed, dict) or not isinstance(metadata, dict):
        raise ActionsCheckError('INVALID_FEED: expected two JSON objects')
    expected = build_feed(notices, generated_at=feed.get('generated_at'))
    expected_metadata = {'schema_version': expected['schema_version'], 'generated_at': expected['generated_at'],
                         'notice_count': len(expected['notices'])}
    # JSON equality also compares number/bool as equal: explicitly retain schema/count types.
    if (feed != expected or metadata != expected_metadata
        or type(feed.get('schema_version')) is not int
        or type(metadata.get('schema_version')) is not int
        or any(type(row.get('is_new')) is not bool for row in feed.get('notices', []))
        or type(metadata.get('notice_count')) is not int):
        raise ActionsCheckError('FEED_SNAPSHOT_MISMATCH: refuse stale or inconsistent publication')
    health = public_source_status(statuses, expected['generated_at'])
    target = Path(stage_dir)
    if target.exists():
        raise ActionsCheckError('STAGE_EXISTS: use a fresh empty publication path')
    target.mkdir(parents=True)
    _atomic_json(target/'notices.json', expected)
    _atomic_json(target/'metadata.json', expected_metadata)
    _atomic_json(target/'source_status.json', health)
    (target/'index.html').write_text(PUBLIC_INDEX, encoding='utf-8')
    return expected_metadata


def diagnostics(data_dir):
    """No body/title/reason/raw error, environment values or secret in output."""
    try:
        notices, statuses = validate_state(data_dir)
    except Exception as error:
        # Class names from our validation boundary are useful without exposing
        # file contents, arbitrary exception messages or environment values.
        kind = type(error).__name__
        known = {'ActionsCheckError', 'StorageFormatError', 'StorageSchemaError',
                 'StorageIOError', 'DiffInputError', 'DiffConflictError'}
        return {'state': 'MISSING_OR_INVALID',
                'check': kind if kind in known else 'VALIDATION_ERROR',
                'hint': 'Inspect the first failed Actions step; state was not reset'}
    report = {
        'state': 'VALID', 'stored_notices': len(notices),
        'scrapers': {source: {'status': status['status'], 'notices_found': status.get('notices_found')}
                     for source, status in sorted(statuses.items())},
        'analysis_counts': {status: sum(notice.gemini.status.value == status for notice in notices)
                            for status in ('NOT_ANALYZED', 'SUCCESS', 'FAILED', 'PENDING')},
    }
    report['external_ai_calls'] = 0
    ocr_path = Path(data_dir)/'ocr_diagnostics.json'
    if ocr_path.is_file():
        metrics = _read_json(ocr_path, {})
        allowed = {'targets','success','failed','partial','deferred','unsupported','cache_hits',
                   'ocr_targets','ocr_success','ocr_failed','ocr_characters','elapsed_seconds'}
        report['ocr'] = {source:{k:v for k,v in value.items() if k in allowed and type(v) in (int,float)}
                         for source,value in metrics.items() if source in statuses and isinstance(value,dict)}
    report['prefilter_counts'] = {s:sum(n.analysis.prefilter_status==s for n in notices)
                                  for s in ('CANDIDATE','REVIEW','CLEARLY_UNRELATED')}
    # This file is an operator-only allowlisted metrics document produced by the
    # queue, never copied into metadata.json or Pages.
    path = Path(data_dir)/'analysis_diagnostics.json'
    if path.is_file():
        metrics = _read_json(path,{})
        report['metrics_phase'] = metrics.get('metrics_phase','UNKNOWN')
        report['stages'] = {name:metrics.get(name+'_status','UNKNOWN')
                            for name in ('collection','prefilter','analysis','publication')}
        allowed = {'api_requests','analyzed_notices','successful_notices','failed_notices','input_tokens',
            'output_tokens','estimated_input_tokens','retries','http_429','http_503','timeouts','cache_hits',
            'quota_scope','quota_limit','quota_metrics','model_id','unique_analyzed_notices','stop_reason','elapsed_seconds'}
        report['gemini'] = {k:v for k,v in metrics.get('gemini',{}).items() if k in allowed}
    return report


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
