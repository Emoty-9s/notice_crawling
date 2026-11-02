"""M13 local-only SQLite performance records. No network/AI/feed imports."""

from __future__ import annotations

import csv
import json
import math
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, fields
from pathlib import Path


DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / 'local' / 'performance.db'
SCHEMA_VERSION = 1
APPLICATION_ID = 0x50455246  # PERF; reject unrelated databases instead of modifying them.


class PerformanceError(Exception):
    """Safe fixed diagnostics; never include record/CSV/SQL exception contents."""


class PerformanceValidationError(PerformanceError):
    pass


class PerformanceDatabaseError(PerformanceError):
    pass


class DuplicatePerformanceError(PerformanceError):
    pass


class PerformanceNotFoundError(PerformanceError):
    pass


class CSVImportError(PerformanceError):
    def __init__(self, code, *, line=None):
        self.code, self.line = code, line
        super().__init__(code + (f' at CSV line {line}' if line is not None else ''))


def _text(value, *, required=False):
    if not isinstance(value, str) or '\x00' in value or (required and not value.strip()):
        raise PerformanceValidationError('INVALID_PERFORMANCE_TEXT')
    try:
        value.encode('utf-8')
    except UnicodeError:
        raise PerformanceValidationError('INVALID_PERFORMANCE_TEXT') from None
    return value


def _year(value):
    if value is not None and (type(value) is not int or not 1 <= value <= 9999):
        raise PerformanceValidationError('INVALID_PERFORMANCE_YEAR')
    return value


def _strings(value):
    if not isinstance(value, (tuple, list)):
        raise PerformanceValidationError('INVALID_PERFORMANCE_LIST')
    return tuple(_text(item, required=True).strip() for item in value)


@dataclass(frozen=True, kw_only=True)
class Performance:
    performance_id: str
    project_name: str
    client: str = ''
    year: int | None = None
    technical_field: str = ''
    work_type: str = ''
    keywords: tuple[str, ...] = ()
    description: str = ''
    attorneys: tuple[str, ...] = ()
    notes: str = ''

    def __post_init__(self):
        for name in ('performance_id', 'project_name', 'client', 'technical_field', 'work_type', 'description', 'notes'):
            value = _text(getattr(self, name), required=name in ('performance_id', 'project_name'))
            if name not in ('description', 'notes'):
                value = value.strip()
            object.__setattr__(self, name, value)
        _year(self.year)
        for name in ('keywords', 'attorneys'):
            object.__setattr__(self, name, _strings(getattr(self, name)))


COLUMNS = tuple(field.name for field in fields(Performance))
_COLUMN_SQL = ', '.join(COLUMNS)  # Fixed internal identifiers only.
_INSERT_SQL = f'INSERT INTO performances ({_COLUMN_SQL}) VALUES ({", ".join("?" for _ in COLUMNS)})'
_CREATE_SQL = '''CREATE TABLE performances (
    performance_id TEXT NOT NULL PRIMARY KEY CHECK(length(trim(performance_id)) > 0),
    project_name TEXT NOT NULL CHECK(length(trim(project_name)) > 0),
    client TEXT NOT NULL,
    year INTEGER CHECK(year IS NULL OR (typeof(year) = 'integer' AND year BETWEEN 1 AND 9999)),
    technical_field TEXT NOT NULL,
    work_type TEXT NOT NULL,
    keywords TEXT NOT NULL,
    description TEXT NOT NULL,
    attorneys TEXT NOT NULL,
    notes TEXT NOT NULL
)'''


def _values(record):
    if not isinstance(record, Performance):
        raise PerformanceValidationError('EXPECTED_PERFORMANCE')
    return tuple(json.dumps(getattr(record, name), ensure_ascii=False) if name in ('keywords', 'attorneys')
                 else getattr(record, name) for name in COLUMNS)


def _record(row):
    try:
        data = dict(row)
        for name in ('keywords', 'attorneys'):
            data[name] = json.loads(data[name])
        return Performance(**data)
    except (ValueError, TypeError, RecursionError, PerformanceValidationError):
        raise PerformanceDatabaseError('INVALID_STORED_PERFORMANCE') from None


def _insert(connection, record):
    try:
        connection.execute(_INSERT_SQL, _values(record))
    except sqlite3.IntegrityError as error:
        if error.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY:
            raise DuplicatePerformanceError('DUPLICATE_PERFORMANCE_ID') from None
        raise PerformanceDatabaseError('DATABASE_CONSTRAINT_FAILED') from None


class PerformanceStore:
    """Initialize/validate schema explicitly; one short transaction per operation.

    get returns None and delete returns False for absent IDs. update replaces the
    full record for its immutable ID; use dataclasses.replace for partial edits.
    """

    def __init__(self, path=None, *, timeout=5):
        if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                or not math.isfinite(timeout) or timeout < 0):
            raise PerformanceValidationError('INVALID_DATABASE_TIMEOUT')
        self.path = Path(path if path is not None else DEFAULT_DB_PATH).resolve()
        self.timeout = timeout
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._connection(initialize=True) as connection:
                connection.execute('BEGIN IMMEDIATE')
                objects = connection.execute("SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
                version = connection.execute('PRAGMA user_version').fetchone()[0]
                app = connection.execute('PRAGMA application_id').fetchone()[0]
                if not objects and version == 0 and app == 0:
                    connection.execute(_CREATE_SQL)
                    connection.execute(f'PRAGMA user_version = {SCHEMA_VERSION}')
                    connection.execute(f'PRAGMA application_id = {APPLICATION_ID}')
                self._verify(connection)
                if [row[0] for row in connection.execute('PRAGMA quick_check')] != ['ok']:
                    raise PerformanceDatabaseError('DATABASE_INTEGRITY_FAILED')
        except OSError:
            raise PerformanceDatabaseError('DATABASE_OPEN_FAILED') from None

    @contextmanager
    def _connection(self, *, initialize=False):
        connection = None
        try:
            # Normal operations must not silently recreate a deleted database.
            target = str(self.path) if initialize else self.path.as_uri() + '?mode=rw'
            connection = sqlite3.connect(target, timeout=self.timeout, uri=not initialize)
            connection.row_factory = sqlite3.Row
            connection.create_function('casefold', 1, lambda value: str(value).casefold(), deterministic=True)
            with connection:
                if not initialize:
                    self._verify(connection)
                yield connection
        except sqlite3.Error:
            raise PerformanceDatabaseError('DATABASE_OPERATION_FAILED') from None
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _verify(connection):
        if (connection.execute('PRAGMA user_version').fetchone()[0] != SCHEMA_VERSION
                or connection.execute('PRAGMA application_id').fetchone()[0] != APPLICATION_ID):
            raise PerformanceDatabaseError('UNSUPPORTED_DATABASE_SCHEMA')
        actual = [(row['name'], row['type'], row['notnull'], row['pk'])
                  for row in connection.execute('PRAGMA table_info(performances)')]
        expected = [(name, 'INTEGER' if name == 'year' else 'TEXT', int(name != 'year'), int(name == 'performance_id'))
                    for name in COLUMNS]
        if actual != expected:
            raise PerformanceDatabaseError('INVALID_DATABASE_SCHEMA')

    def create(self, record):
        _values(record)  # Validate before any write/lock.
        with self._connection() as connection:
            _insert(connection, record)
        return record

    def get(self, performance_id):
        identity = _text(performance_id, required=True).strip()
        with self._connection() as connection:
            row = connection.execute(f'SELECT {_COLUMN_SQL} FROM performances WHERE performance_id = ?', (identity,)).fetchone()
            return None if row is None else _record(row)

    def update(self, record):
        values = _values(record)
        assignments = ', '.join(f'{name} = ?' for name in COLUMNS[1:])
        with self._connection() as connection:
            cursor = connection.execute(f'UPDATE performances SET {assignments} WHERE performance_id = ?', values[1:] + values[:1])
            if cursor.rowcount == 0:
                raise PerformanceNotFoundError('PERFORMANCE_NOT_FOUND')
        return record

    def delete(self, performance_id):
        identity = _text(performance_id, required=True).strip()
        with self._connection() as connection:
            return connection.execute('DELETE FROM performances WHERE performance_id = ?', (identity,)).rowcount == 1

    def search(self, query='', *, year=None, limit=100, offset=0):
        """Literal Unicode case-insensitive substring search; no scoring/matching."""
        _text(query)
        _year(year)
        if type(limit) is not int or limit <= 0 or type(offset) is not int or offset < 0:
            raise PerformanceValidationError('INVALID_SEARCH_PAGE')
        condition = ' OR '.join(f'instr(casefold(coalesce({name}, \'\')), casefold(?)) > 0' for name in COLUMNS)
        sql = f'SELECT {_COLUMN_SQL} FROM performances WHERE ({condition})'
        parameters = [query.strip()] * len(COLUMNS)
        if year is not None:
            sql += ' AND year = ?'
            parameters.append(year)
        sql += ' ORDER BY year DESC, performance_id ASC LIMIT ? OFFSET ?'
        parameters.extend((limit, offset))
        with self._connection() as connection:
            return [_record(row) for row in connection.execute(sql, parameters)]

    def import_csv(self, path, *, encoding='utf-8-sig'):
        """Strict headers; keywords/attorneys separated by semicolons. All-or-none."""
        parsed = []
        reader = None
        try:
            with Path(path).open('r', encoding=encoding, newline='') as handle:
                reader = csv.DictReader(handle, strict=True)
                header = reader.fieldnames
                if header is None or len(header) != len(COLUMNS) or set(header) != set(COLUMNS):
                    raise CSVImportError('INVALID_CSV_HEADER', line=1)
                identities = set()
                for row in reader:
                    line = reader.line_num
                    if None in row or any(value is None for value in row.values()):
                        raise CSVImportError('INVALID_CSV_ROW', line=line)
                    try:
                        raw_year = row['year'].strip()
                        if raw_year and (not raw_year.isascii() or not raw_year.isdigit()):
                            raise ValueError('invalid year')
                        row['year'] = int(raw_year) if raw_year else None
                        for name in ('keywords', 'attorneys'):
                            row[name] = tuple(item.strip() for item in row[name].split(';') if item.strip())
                        record = Performance(**row)
                    except (ValueError, PerformanceValidationError):
                        raise CSVImportError('INVALID_CSV_ROW', line=line) from None
                    if record.performance_id in identities:
                        raise CSVImportError('DUPLICATE_CSV_ID', line=line)
                    identities.add(record.performance_id)
                    parsed.append((line, record))
        except (OSError, UnicodeError, LookupError):
            raise CSVImportError('CSV_READ_FAILED') from None
        except csv.Error:
            raise CSVImportError('MALFORMED_CSV', line=reader.line_num if reader else None) from None
        # Validation/read failures occur before the write transaction starts.
        with self._connection() as connection:
            for line, record in parsed:
                try:
                    _insert(connection, record)
                except DuplicatePerformanceError:
                    raise CSVImportError('DUPLICATE_PERFORMANCE_ID', line=line) from None
        return len(parsed)
