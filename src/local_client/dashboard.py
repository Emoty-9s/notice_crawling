"""M15 read-only performance loading, retained cache and M14 presentation."""

import copy
import json
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from . import matcher
from .performance import APPLICATION_ID, COLUMNS, SCHEMA_VERSION, Performance, PerformanceValidationError
from .sync import FeedClient, SyncError, validate_pair, retained_snapshot


RULE_LABELS = {
    'technical_field': '기술분야', 'work_type': '업무유형', 'keyword': '키워드',
    'category': '카테고리', 'title': '제목 핵심어', 'recent': '최근 실적',
}


class DashboardError(ValueError):
    """Safe code only; never report raw SQL/CSV/private data exceptions."""


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def _constant(value):
    raise ValueError('nonstandard JSON constant')


def _load_cache(path, *, today=None):
    try:
        snapshot = json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=_pairs, parse_constant=_constant)
        json.dumps(snapshot, ensure_ascii=False, allow_nan=False).encode('utf-8')
        if (not isinstance(snapshot, dict) or set(snapshot) != {'base_url', 'feed', 'metadata'}
                or not isinstance(snapshot['base_url'], str) or not snapshot['base_url'].strip()):
            raise ValueError('invalid cache envelope')
        if FeedClient(snapshot['base_url']).base_url != snapshot['base_url']:
            raise ValueError('noncanonical cache source')
        validate_pair(snapshot['feed'], snapshot['metadata'])
        retained = retained_snapshot(snapshot, today=today)
        return retained
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError, SyncError):
        raise DashboardError('INVALID_OR_MISSING_CACHE') from None


def _load_performances(path):
    # PerformanceStore initializes missing databases. The UI must never do so;
    # adapt the existing M13 schema to its public immutable Performance model
    # using an OS/SQLite read-only connection, without CRUD or schema changes.
    try:
        uri = Path(path).resolve().as_uri() + '?mode=ro'
        with closing(sqlite3.connect(uri, uri=True, timeout=5)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute('PRAGMA query_only = ON')
            connection.execute('BEGIN')
            if (connection.execute('PRAGMA application_id').fetchone()[0] != APPLICATION_ID
                    or connection.execute('PRAGMA user_version').fetchone()[0] != SCHEMA_VERSION
                    or tuple(row['name'] for row in connection.execute('PRAGMA table_info(performances)')) != COLUMNS):
                raise ValueError('unsupported schema')
            records = []
            for row in connection.execute('SELECT ' + ', '.join(COLUMNS) + ' FROM performances ORDER BY performance_id'):
                data = dict(row)
                for name in ('keywords', 'attorneys'):
                    data[name] = json.loads(data[name])
                records.append(Performance(**data))
            return tuple(records)
    except (sqlite3.Error, OSError, ValueError, TypeError, RecursionError, PerformanceValidationError):
        raise DashboardError('INVALID_OR_MISSING_DATABASE') from None


@dataclass(frozen=True)
class DashboardData:
    snapshot: dict
    performances: tuple[Performance, ...]


def load_dashboard(cache_path, database_path, *, clock=None):
    """Load local data and project active rows without rewriting the cache."""
    snapshot = _load_cache(cache_path, today=clock() if clock else None)
    performances = _load_performances(database_path)
    return DashboardData(snapshot, performances)


def notice_rows(data, *, query='', institution='', category=''):
    """Preserve feed order. Filters only change displayed rows, not the source."""
    if any(not isinstance(value, str) for value in (query, institution, category)):
        raise DashboardError('INVALID_FILTER')
    query = query.strip().casefold()
    rows = []
    for notice in data.snapshot['feed']['notices']:
        from .notice_analysis import adapt_notice
        notice = adapt_notice(notice)
        if institution and notice['institution'] != institution:
            continue
        if category and notice['category'] != category:
            continue
        text = ' '.join([notice['notice_id'], notice['title'], notice['category'], notice['participation_type'],
                         notice['institution'], notice['summary'], *notice['keywords']]).casefold()
        if not query or query in text:
            rows.append(copy.deepcopy(notice))
    return rows


def _integer(value, minimum, maximum, code):
    if isinstance(value, str) and re.fullmatch(r'[0-9]+', value.strip()):
        try:
            value = int(value.strip())
        except ValueError:
            raise DashboardError(code) from None
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise DashboardError(code)
    return value


def recommendation_rows(data, notice_id, *, reference_year, top_n=5):
    """Join names to the public M14 results; do not recalculate ranking/points."""
    year = _integer(reference_year, 1, 9999, 'INVALID_REFERENCE_YEAR')
    count = _integer(top_n, 0, None, 'INVALID_TOP_N')
    notice = next((row for row in data.snapshot['feed']['notices'] if row['notice_id'] == notice_id), None)
    if notice is None:
        raise DashboardError('SELECT_NOTICE')
    from .notice_analysis import adapt_notice
    notice = adapt_notice(notice)
    try:
        results = matcher.match_notice(notice, data.performances, reference_year=year, top_n=count)
    except matcher.MatchInputError:
        raise DashboardError('MATCH_INPUT_ERROR') from None
    projects = {record.performance_id: record.project_name for record in data.performances}
    rows = []
    for rank, result in enumerate(results, start=1):
        row = result.to_dict()
        row.update(ranking=rank, project_name=projects[result.performance_id], total_score=result.score,
                   rule_total=sum(reason.points for reason in result.reasons))
        row['sum_matches'] = row['total_score'] == row['rule_total']
        rows.append(row)
    return rows


def notice_details(notice):
    return '\n'.join([
        f'공고 ID: {notice["notice_id"]}', f'제목: {notice["title"]}',
        f'기관: {notice["institution"]}', f'category: {notice["category"]}',
        f'participation_type: {notice["participation_type"]}',
        'keywords: ' + ', '.join(notice['keywords']), '', 'summary:', notice['summary'], '',
        '기존 선별 근거: ' + notice['relevance_reason'],
        '원문 URL (표시만): ' + notice['url'],
    ])


def recommendation_details(row):
    lines = [f'{row["ranking"]}위 | {row["performance_id"]} | {row["project_name"]}',
             f'총점 (total_score): {row["total_score"]}점',
             f'규칙별 합계: {row["rule_total"]}점 | ' + ('일치' if row['sum_matches'] else '불일치 — 결과 확인 필요'),
             '일치 용어: ' + ', '.join(row['matched_terms']), '']
    for reason in row['reasons']:
        label = RULE_LABELS.get(reason['rule'], reason['rule'])
        lines.extend([f'{label} ({reason["rule"]}): +{reason["points"]}점',
                      '  근거: ' + ', '.join(reason['terms'])])
    if not row['reasons']:
        lines.append('적용된 가점 규칙 없음')
    return '\n'.join(lines)
