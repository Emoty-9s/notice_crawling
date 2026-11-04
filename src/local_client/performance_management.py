"""Local-only management service. UI never issues SQL or changes identity."""
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from .performance import PerformanceStore, PerformanceValidationError, _COLUMN_SQL, _record, _values
from .upload_store import (load_enrichment_preview, _enrichments, _revision, _ENRICHMENT_CREATE,
                           _write_enrichment, _adapter_keywords, _model_value)
from .technical_labels import selection, validate_row_fields
from .matcher import DEFAULT_CATEGORY_GROUPS


EMPTY_TEXT = '등록된 실적이 없습니다. 실적 업로드를 통해 데이터를 추가하세요.'


def allowed_work_types():
    return tuple(dict.fromkeys(v for group in DEFAULT_CATEGORY_GROUPS for v in group))


def technical_names(row):
    from .technical_labels import allowed_technical_fields
    allowed = allowed_technical_fields()
    return list(dict.fromkeys(v for v in [row.technical_field]+[f['name'] for f in row.technical_fields] if v in allowed))[:3]


class PerformanceManagement:
    def __init__(self, path):
        self.path = Path(path).resolve()

    def list(self, query=''):
        if not self.path.is_file():
            return []  # Viewing an empty list does not create a database.
        rows = load_enrichment_preview(self.path).rows
        query = query.strip().casefold()
        if query:
            rows = [r for r in rows if query in '\n'.join(str(v or '') for v in
                    (r.management_id,r.project_name,r.client,r.technical_field,' · '.join(technical_names(r)),r.work_type)).casefold()]
        return sorted(rows,key=lambda r: (-(r.year or 0),(r.management_id or r.project_name or '').casefold(),
                                           (r.project_name or '').casefold(),r.performance_id))

    def get(self, identity):
        return next((r for r in self.list() if r.performance_id == identity),None)

    def update(self, original, *, year, management_id, project_name, client, technical_fields, work_type):
        from .enrichment import set_user_value, refresh_search
        if year is not None and (type(year) is not int or not 1 <= year <= 9999):
            raise ValueError('INVALID_YEAR')
        if management_id is not None and not isinstance(management_id,str):
            raise ValueError('INVALID_MANAGEMENT_ID')
        if not isinstance(project_name,str) or not project_name.strip() or not isinstance(client,str):
            raise ValueError('INVALID_PROJECT')
        names = selection(' · '.join(technical_fields))
        if work_type not in ('','미분류',*allowed_work_types()):
            raise ValueError('INVALID_WORK_TYPE')
        row = deepcopy(original)
        for field,value in (('year',year),('management_id',management_id or None),
                            ('project_name',project_name.strip()),('client',client.strip())):
            if getattr(row,field) != value:
                setattr(row,field,value)
                row.field_sources[field] = 'user'
                row.field_confidence[field] = None
        if names != technical_names(row) or (row.technical_field or '미분류') != (names[0] if names else '미분류'):
            set_user_value(row,'technical_field',' · '.join(names) or '미분류')
        else:
            row.technical_field = names[0] if names else '미분류'
            row.technical_fields = [v for v in row.technical_fields if v['name'] in names]
        if work_type != (row.work_type or '미분류'):
            set_user_value(row,'work_type',work_type or '미분류')
        validate_row_fields(row)
        # Rebuild current normalized searchable content while retaining original
        # source cells separately. Management ID never becomes matcher text.
        row.match_text = '\n'.join(dict.fromkeys(v for v in (row.project_name,row.client,row.description) if v))
        refresh_search(row)
        store = PerformanceStore(self.path,create=False)
        with store._connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            current = self._current(connection,original)
            record = replace(current,year=row.year,project_name=row.project_name,client=row.client or '',
                             technical_field=_model_value(row.technical_field),work_type=_model_value(row.work_type),
                             keywords=_adapter_keywords(row),description=row.match_text)
            values = _values(record)
            assignments = ', '.join(f'{name}=?' for name in _COLUMN_SQL.split(', ')[1:])
            connection.execute('UPDATE performances SET '+assignments+' WHERE performance_id=?',values[1:]+values[:1])
            connection.execute(_ENRICHMENT_CREATE)
            _write_enrichment(connection,original.performance_id,row)
            if self._has_table(connection,'performance_uploads_v1'):
                upload = connection.execute('SELECT normalized FROM performance_uploads_v1 WHERE performance_id=?',
                                            (original.performance_id,)).fetchone()
                if upload:
                    normalized = json.loads(upload[0])
                    for field in ('management_id','year','project_name','client','technical_field','work_type'):
                        normalized[field] = getattr(row,field)
                    connection.execute('UPDATE performance_uploads_v1 SET management_id=?,normalized=?,searchable_text=? WHERE performance_id=?',
                        (row.management_id,json.dumps(normalized,ensure_ascii=False),row.searchable_text,original.performance_id))
        return self.get(original.performance_id)

    @staticmethod
    def _has_table(connection,name):
        return bool(connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone())

    @staticmethod
    def _current(connection,row):
        found = connection.execute('SELECT '+_COLUMN_SQL+' FROM performances WHERE performance_id=?',(row.performance_id,)).fetchone()
        current = _record(found) if found else None
        metadata = _enrichments(connection).get(row.performance_id,{})
        if current is None or _revision(current,metadata) != row.base_revision:
            raise ValueError('RECORD_CHANGED')
        return current

    def delete(self, rows):
        rows = list({r.performance_id:r for r in rows}.values())
        if not rows:
            return 0
        store = PerformanceStore(self.path,create=False)
        with store._connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            for row in rows:
                self._current(connection,row)
            for row in rows:
                # FK cascades on current tables; explicit cleanup also supports
                # older companions without FK definitions, within one transaction.
                for table in ('performance_enrichment_v1','performance_uploads_v1'):
                    if self._has_table(connection,table):
                        connection.execute(f'DELETE FROM {table} WHERE performance_id=?',(row.performance_id,))
                connection.execute('DELETE FROM performances WHERE performance_id=?',(row.performance_id,))
        return len(rows)
