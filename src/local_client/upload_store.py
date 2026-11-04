"""Local-only upload persistence beside the unchanged Performance v1 table."""
import json
import sqlite3
from copy import deepcopy
from dataclasses import dataclass, asdict, replace
from hashlib import sha256

from .performance import (Performance, PerformanceStore, PerformanceValidationError,
                          _values, _INSERT_SQL, _record, _COLUMN_SQL)
from .upload import UploadPreview, UploadRow, canonical
from .technical_labels import validate_row_fields


_CREATE = '''CREATE TABLE IF NOT EXISTS performance_uploads_v1 (
    performance_id TEXT PRIMARY KEY REFERENCES performances(performance_id) ON DELETE CASCADE,
    management_id TEXT,
    start_date TEXT,
    end_date TEXT,
    amount TEXT,
    raw_source TEXT NOT NULL,
    searchable_text TEXT NOT NULL,
    fingerprint TEXT NOT NULL UNIQUE,
    source_filename TEXT NOT NULL,
    sheet_name TEXT NOT NULL,
    source_row INTEGER NOT NULL,
    issues TEXT NOT NULL,
    mappings TEXT NOT NULL,
    normalized TEXT NOT NULL
)'''


@dataclass(frozen=True)
class ImportResult:
    saved: int
    review: int
    duplicates: int
    failed: int
    failed_rows: tuple[tuple[str, int, str], ...]
    updated: int = 0


_ENRICHMENT_CREATE = '''CREATE TABLE IF NOT EXISTS performance_enrichment_v1 (
    performance_id TEXT PRIMARY KEY REFERENCES performances(performance_id) ON DELETE CASCADE,
    data TEXT NOT NULL
)'''


def enrichment_data(row):
    result = {name: getattr(row, name) for name in ('field_sources', 'field_confidence', 'ai_model_version',
        'normalization_version', 'review_required', 'technical_fields', 'ai_evidence', 'issues')}
    result['ai_evidence'] = deepcopy(row.ai_evidence)
    if row.technical_tags:
        result['ai_evidence'].setdefault('technical_field', {})['source_terms'] = deepcopy(row.technical_tags)
    result['inferred_values'] = {name: getattr(row, name) for name in ('project_name', 'technical_field', 'work_type', 'keywords')}
    result['local_values'] = {'management_id': row.management_id}
    if row.raw_source.get('legacy_record'):
        result['local_values']['raw_source'] = deepcopy(row.raw_source)
    return result


def _write_enrichment(connection, identity, row):
    connection.execute('INSERT OR REPLACE INTO performance_enrichment_v1 VALUES (?, ?)',
                       (identity, json.dumps(enrichment_data(row), ensure_ascii=False, allow_nan=False)))


def _enrichments(connection):
    if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='performance_enrichment_v1'").fetchone():
        return {}
    from .performance import PerformanceDatabaseError
    try:
        data = {row[0]: json.loads(row[1]) for row in connection.execute('SELECT performance_id, data FROM performance_enrichment_v1')}
        if any(not isinstance(value, dict) or not isinstance(value.get('field_sources'), dict) for value in data.values()):
            raise ValueError()
        return data
    except (TypeError, ValueError):
        raise PerformanceDatabaseError('INVALID_ENRICHMENT_METADATA') from None


def _revision(record, metadata):
    return sha256(json.dumps([asdict(record), metadata], sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _adapter_keywords(row):
    values = []
    if row.field_sources.get('technical_field') in ('local_model', 'user', 'deterministic_mapping') and row.technical_field != '미분류':
        for tag in row.technical_fields:
            values.append(tag['name'])
            values += [v.strip() for v in tag['name'].split(' / ') if v.strip()]
            values += [v.strip() for v in tag.get('category', '').split(' / ') if v.strip()]
        values += [word.strip() for word in row.technical_field.split(' / ') if word.strip()]
        values += [tag['name'] for tag in row.technical_tags]
    values += list(row.keywords)
    return tuple(dict.fromkeys(values))[:15]


def _model_value(value):
    return '' if value == '미분류' else value


def _business_key(project_name, client, year):
    # A management ID alone cannot identify records across companies. Without
    # sufficient business context, deduplicate only an exact content fingerprint.
    if project_name and client and year is not None:
        return canonical(project_name), canonical(client), year
    return None


def _management_key(management_id, project_name, client, year):
    if management_id and project_name and client:
        return canonical(management_id), canonical(project_name), canonical(client), year
    return None


def save_preview(database_path, preview):
    if not isinstance(preview, UploadPreview):
        raise PerformanceValidationError('INVALID_UPLOAD_PREVIEW')
    store = PerformanceStore(database_path)
    saved = review = duplicates = 0
    failed_rows = []
    with store._connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        connection.execute(_CREATE)
        connection.execute(_ENRICHMENT_CREATE)
        existing = [_record(row) for row in connection.execute('SELECT ' + _COLUMN_SQL + ' FROM performances')]
        keys = {_business_key(p.project_name, p.client, p.year) for p in existing} - {None}
        projects = {p.performance_id: p for p in existing}
        keyed_projects = {_business_key(p.project_name, p.client, p.year): p.performance_id for p in existing}
        metadata_by_id = _enrichments(connection)
        fingerprints_by_id = {r[0]: r[1] for r in connection.execute('SELECT fingerprint, performance_id FROM performance_uploads_v1')}
        updated = 0
        management_keys = set()
        for identity, management_id in connection.execute('SELECT performance_id, management_id FROM performance_uploads_v1'):
            p = projects.get(identity)
            if p:
                key = _management_key(management_id, p.project_name, p.client, p.year)
                if key is not None:
                    management_keys.add(key)
        fingerprints = {row[0] for row in connection.execute(
            'SELECT u.fingerprint FROM performance_uploads_v1 u JOIN performances p USING (performance_id)')}
        for row in preview.rows:
            try:
                validate_row_fields(row)
            except ValueError:
                failed_rows.append((row.sheet, row.row_number, 'INVALID_TECHNICAL_SELECTION'))
                continue
            key = _business_key(row.project_name, row.client, row.year)
            management_key = _management_key(row.management_id, row.project_name, row.client, row.year)
            if (row.fingerprint in fingerprints or (key is not None and key in keys)
                    or (management_key is not None and management_key in management_keys)):
                duplicates += 1
                identity = fingerprints_by_id.get(row.fingerprint) or keyed_projects.get(key)
                if identity and row.user_edits:
                    current = projects[identity]
                    if row.base_revision and row.base_revision != _revision(current, metadata_by_id.get(identity, {})):
                        failed_rows.append((row.sheet, row.row_number, 'RECORD_CHANGED'))
                        continue
                    changes = {name: _model_value(getattr(row, name)) for name in ('technical_field', 'work_type')
                               if name in row.user_edits}
                    if changes:
                        current_meta = metadata_by_id.get(identity, {})
                        fields = dict(current_meta.get('field_sources', {}))
                        confidence = dict(current_meta.get('field_confidence', {}))
                        for name in changes:
                            fields[name], confidence[name] = 'user', None
                        inferred_values = dict(current_meta.get('inferred_values', {}))
                        for name in changes:
                            inferred_values[name] = getattr(row, name)
                        current_meta.update(field_sources=fields, field_confidence=confidence)
                        current_meta['inferred_values'] = inferred_values
                        if 'technical_field' in changes:
                            current_meta['technical_fields'] = deepcopy(row.technical_fields)
                            current_meta.pop('technical_tags', None)
                            current_meta.setdefault('ai_evidence', {})['technical_field'] = {'source_terms': deepcopy(row.technical_tags)}
                        for name, value in changes.items():
                            connection.execute(f'UPDATE performances SET {name}=? WHERE performance_id=?', (value, identity))
                        if 'technical_field' in changes:
                            connection.execute('UPDATE performances SET keywords=? WHERE performance_id=?',
                                               (json.dumps(_adapter_keywords(row), ensure_ascii=False), identity))
                        connection.execute('INSERT OR REPLACE INTO performance_enrichment_v1 VALUES (?, ?)',
                                           (identity, json.dumps(current_meta, ensure_ascii=False)))
                        updated += 1
                continue
            connection.execute('SAVEPOINT upload_row')
            try:
                record = Performance(
                    performance_id='upload:v1:' + row.fingerprint,
                    project_name=row.project_name or f'이름 미확인 ({row.sheet} {row.row_number}행)',
                    client=row.client or '', year=row.year, technical_field=_model_value(row.technical_field),
                    work_type=_model_value(row.work_type), keywords=_adapter_keywords(row),
                    description=row.match_text)
                connection.execute(_INSERT_SQL, _values(record))
                connection.execute('''INSERT INTO performance_uploads_v1 VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (record.performance_id, row.management_id, row.start_date, row.end_date, row.amount,
                     json.dumps(row.raw_source, ensure_ascii=False, allow_nan=False), row.searchable_text,
                     row.fingerprint, preview.filename, row.sheet, row.row_number,
                     json.dumps(row.issues, ensure_ascii=False),
                     json.dumps(preview.mappings.get(row.sheet, {}), ensure_ascii=False),
                     json.dumps({name: getattr(row, name) for name in
                        ('management_id', 'project_name', 'client', 'start_date', 'end_date', 'year',
                         'technical_field', 'work_type', 'description', 'keywords', 'amount')}, ensure_ascii=False)))
                _write_enrichment(connection, record.performance_id, row)
                connection.execute('RELEASE upload_row')
                fingerprints.add(row.fingerprint)
                fingerprints_by_id[row.fingerprint] = record.performance_id
                projects[record.performance_id] = record
                metadata_by_id[record.performance_id] = enrichment_data(row)
                if key is not None:
                    keys.add(key)
                    keyed_projects[key] = record.performance_id
                if management_key is not None:
                    management_keys.add(management_key)
                saved += 1
                review += bool(row.issues)
            except (PerformanceValidationError, sqlite3.IntegrityError, ValueError, TypeError):
                connection.execute('ROLLBACK TO upload_row')
                connection.execute('RELEASE upload_row')
                failed_rows.append((row.sheet, row.row_number, 'INVALID_ROW'))
    return ImportResult(saved, review, duplicates, len(failed_rows), tuple(failed_rows), updated)


def load_enrichment_preview(database_path):
    """Read existing records without initializing/migrating the user's DB."""
    from .dashboard import _load_performances
    from contextlib import closing
    from pathlib import Path
    records = _load_performances(database_path)
    with closing(sqlite3.connect(Path(database_path).resolve().as_uri()+'?mode=ro', uri=True)) as connection:
        metadata = _enrichments(connection)
        has_upload = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='performance_uploads_v1'").fetchone()
        if has_upload:
            connection.row_factory = sqlite3.Row
            uploads = {r['performance_id']: dict(r) for r in connection.execute('SELECT * FROM performance_uploads_v1')}
        else:
            uploads = {}
    rows = []
    for p in records:
        uploaded = uploads.get(p.performance_id, {})
        normalized = json.loads(uploaded.get('normalized', '{}'))
        meta = metadata.get(p.performance_id, {})
        raw = json.loads(uploaded['raw_source']) if 'raw_source' in uploaded else json.loads(json.dumps({'columns': asdict(p), 'legacy_record': True},ensure_ascii=False))
        row = UploadRow(uploaded.get('sheet_name', '기존 DB'), uploaded.get('source_row', len(rows)+1),
            normalized.get('management_id'), normalized.get('project_name', p.project_name), p.client,
            normalized.get('start_date'), normalized.get('end_date'), p.year, p.technical_field, p.work_type,
            normalized.get('description', p.description), tuple(normalized.get('keywords', p.keywords)),
            normalized.get('amount'), raw, uploaded.get('searchable_text', p.description), p.description,
            uploaded.get('fingerprint', p.performance_id), json.loads(uploaded.get('issues', '[]')))
        for name, value in meta.items():
            if name in enrichment_data(row) and name not in ('inferred_values','local_values'):
                setattr(row, name, deepcopy(value))
        row.management_id = meta.get('local_values',{}).get('management_id',row.management_id)
        row.raw_source = deepcopy(meta.get('local_values',{}).get('raw_source',row.raw_source))
        for name, value in meta.get('inferred_values', {}).items():
            if name in ('project_name', 'technical_field', 'work_type', 'keywords'):
                setattr(row, name, tuple(value) if name == 'keywords' else value)
        row.technical_tags = deepcopy(meta.get('technical_tags') or row.ai_evidence.get('technical_field', {}).get('source_terms')
                                      or row.ai_evidence.get('technical_field', {}).get('tags') or [])
        # Existing DAO/API edits also outrank an old AI metadata snapshot.
        for name in ('project_name', 'technical_field', 'work_type'):
            expected = meta.get('inferred_values', {}).get(name, getattr(p, name))
            if name == 'project_name' and not expected and p.project_name.startswith('이름 미확인 ('):
                continue
            if getattr(p, name) != _model_value(expected):
                setattr(row, name, getattr(p, name))
                row.field_sources[name] = 'legacy_explicit'
                row.field_confidence[name] = 1.0
                if name == 'technical_field':
                    row.technical_fields = []
                    row.technical_tags = []
        # v2 stored detailed tags in technical_fields. Adapt that representation
        # in memory, then persist only after the existing explicit Save action.
        if any('category' in v for v in row.technical_fields):
            old_tags = row.technical_fields
            row.technical_tags = old_tags[:3]
            row.technical_fields = list({v.get('category', v['name']):
                {'name': v.get('category', v['name']), 'source': v.get('source', 'local_model'), 'score': v.get('score')}
                for v in old_tags}.values())[:3]
            if row.field_sources.get('technical_field') == 'deterministic_mapping':
                row.technical_field = row.technical_fields[0]['name']
        for name in ('management_id', 'project_name', 'client', 'start_date', 'end_date', 'year',
                     'technical_field', 'work_type', 'description', 'keywords', 'amount'):
            row.field_sources.setdefault(name, 'legacy_explicit' if getattr(row, name) not in (None, '', ()) else 'unknown')
            row.field_confidence.setdefault(name, 1.0 if row.field_sources[name] == 'legacy_explicit' else None)
        row.performance_id = p.performance_id
        row.base_revision = _revision(p, meta)
        rows.append(row)
    return UploadPreview('기존 로컬 실적 DB', len({r.sheet for r in rows}), rows, 0, [], {})


def restore_saved_enrichment(preview, database_path):
    from pathlib import Path
    if not Path(database_path).is_file():
        return
    existing = load_enrichment_preview(database_path)
    fingerprints = {r.fingerprint: r for r in existing.rows}
    from .enrichment import refresh_search
    for row in preview.rows:
        previous = fingerprints.get(row.fingerprint)
        if previous is None:
            continue
        for name in ('project_name', 'technical_field', 'work_type', 'keywords'):
            if previous.field_sources.get(name) in ('user', 'local_model', 'deterministic_mapping'):
                setattr(row, name, getattr(previous, name))
                row.field_sources[name] = previous.field_sources[name]
                row.field_confidence[name] = previous.field_confidence.get(name)
        for name in ('ai_model_version', 'normalization_version', 'technical_fields', 'technical_tags', 'ai_evidence'):
            setattr(row, name, getattr(previous, name))
        row.issues = list(dict.fromkeys(row.issues+[issue for issue in previous.issues if issue.startswith('로컬 AI ')]))
        row.review_required = bool(row.issues) or previous.review_required
        row.performance_id = previous.performance_id
        row.base_revision = previous.base_revision
        refresh_search(row)


def save_enriched_preview(database_path, preview):
    """Explicit reanalysis save; optimistic locking protects later user edits."""
    from .enrichment import MODEL_FIELDS
    store = PerformanceStore(database_path)
    updated = failed = review = 0
    failures = []
    with store._connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        connection.execute(_ENRICHMENT_CREATE)
        metadata = _enrichments(connection)
        for row in preview.rows:
            try:
                validate_row_fields(row)
            except ValueError:
                failures.append((row.sheet, row.row_number, 'INVALID_TECHNICAL_SELECTION'))
                continue
            result = connection.execute('SELECT '+_COLUMN_SQL+' FROM performances WHERE performance_id=?', (row.performance_id,)).fetchone()
            if result is None:
                failures.append((row.sheet, row.row_number, 'RECORD_CHANGED'))
                continue
            current = _record(result)
            old_meta = metadata.get(row.performance_id, {})
            if _revision(current, old_meta) != row.base_revision:
                failures.append((row.sheet, row.row_number, 'RECORD_CHANGED'))
                continue
            changes = {}
            for name in MODEL_FIELDS:
                old_source = old_meta.get('field_sources', {}).get(name, 'legacy_explicit' if getattr(current, name) else 'unknown')
                source = row.field_sources.get(name)
                legacy_unknown = (name == 'technical_field' and current.technical_field in ('', None, '미분류') and old_source != 'user')
                if source == 'user' or (source in ('local_model', 'unknown', 'deterministic_mapping') and (old_source in ('local_model', 'unknown', 'deterministic_mapping') or legacy_unknown)):
                    value = getattr(row, name)
                    if name == 'project_name' and not value:
                        continue
                    changes[name] = _adapter_keywords(row) if name == 'keywords' else _model_value(value)
            if 'technical_field' in changes:
                # Keep explicit/user keywords intact while exposing all approved
                # broad fields and source tags to the unchanged matcher.
                changes['keywords'] = tuple(dict.fromkeys([
                    *changes.get('keywords', current.keywords), *_adapter_keywords(row)]))
            connection.execute('SAVEPOINT enrichment_row')
            try:
                record = replace(current, **changes)
                values = _values(record)
                assignments = ', '.join(f'{name}=?' for name in _COLUMN_SQL.split(', ')[1:])
                connection.execute('UPDATE performances SET '+assignments+' WHERE performance_id=?', values[1:]+values[:1])
                _write_enrichment(connection, row.performance_id, row)
                # Original raw_source and original normalization columns stay intact.
                connection.execute('RELEASE enrichment_row')
                updated += 1
                review += row.review_required
            except (PerformanceValidationError, ValueError, TypeError, sqlite3.IntegrityError):
                connection.execute('ROLLBACK TO enrichment_row')
                connection.execute('RELEASE enrichment_row')
                failures.append((row.sheet, row.row_number, 'INVALID_ROW'))
    return ImportResult(0, review, 0, len(failures), tuple(failures), updated)
