"""M06 JSON snapshots with strict validation and per-file atomic replacement.

No scraping, status inference, diff, Gemini calls or pipeline integration.
Each save is one explicit snapshot, not a transaction across the two files.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import fields
from pathlib import Path
from typing import TextIO

from src.core.models import GeminiResult, Notice


class StorageError(Exception):
    """Base error; callers decide how to report/recover without resetting data."""


class StorageFormatError(StorageError):
    """Malformed UTF-8/JSON, duplicate JSON keys or nonstandard constants."""


class StorageSchemaError(StorageError):
    """Valid JSON or caller input that violates the storage data contract."""


class StorageIOError(StorageError):
    """Read/write/flush/replace failed; the underlying OSError is __cause__."""


def _object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON object key')
        result[key] = value
    return result


def _constant(value: str):
    raise ValueError(f'nonstandard JSON constant: {value}')


def _read_json(path: Path, empty):
    try:
        text = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return empty
    except UnicodeDecodeError as error:
        raise StorageFormatError(f'{path}: invalid UTF-8') from error
    except OSError as error:
        raise StorageIOError(f'{path}: read failed') from error
    try:
        return json.loads(text, object_pairs_hook=_object, parse_constant=_constant)
    except (ValueError, RecursionError) as error:
        raise StorageFormatError(f'{path}: invalid JSON') from error


def _notice_records(data: object) -> list[Notice]:
    if not isinstance(data, list):
        raise StorageSchemaError('notices must be a JSON array')
    notice_keys = {f.name for f in fields(Notice)}
    gemini_keys = {f.name for f in fields(GeminiResult)}
    legacy_gemini_keys = gemini_keys - {'participation_type', 'keywords'}
    notices = []
    for index, record in enumerate(data):
        if not isinstance(record, dict) or set(record) != notice_keys:
            raise StorageSchemaError(f'notice[{index}]: incomplete/unknown Notice fields')
        gemini = record['gemini']
        if not isinstance(gemini, dict) or set(gemini) not in (gemini_keys, legacy_gemini_keys):
            raise StorageSchemaError(f'notice[{index}]: incomplete/unknown Gemini fields')
        try:
            notices.append(Notice.from_dict(record))
        except (TypeError, ValueError) as error:
            raise StorageSchemaError(f'notice[{index}]: invalid model values') from error
    return notices


_STATUS_FIELDS = {
    'status', 'last_attempt_at', 'last_success_at', 'notices_found',
    'error_type', 'error_message',
}
_TEXT_STATUS_FIELDS = {'last_attempt_at', 'last_success_at', 'error_type', 'error_message'}


def _status_records(data: object) -> dict:
    """Validate a source_id -> status record mapping; preserve absent/null fields.

    status is required (SUCCESS/ERROR/WARNING). Remaining fields are optional.
    This only stores values; choosing status and detecting warnings is not M06.
    """
    if not isinstance(data, dict):
        raise StorageSchemaError('scraper status must be a JSON object')
    for source_id, record in data.items():
        if not isinstance(source_id, str) or not source_id.strip():
            raise StorageSchemaError('scraper status requires nonempty source_id keys')
        if not isinstance(record, dict) or 'status' not in record or set(record) - _STATUS_FIELDS:
            raise StorageSchemaError('invalid scraper status fields')
        status = record['status']
        if not isinstance(status, str) or status not in ('SUCCESS', 'ERROR', 'WARNING'):
            raise StorageSchemaError('invalid scraper status value')
        for key in _TEXT_STATUS_FIELDS & record.keys():
            value = record[key]
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise StorageSchemaError(f'{key} must be nonempty text or null')
        count = record.get('notices_found')
        if count is not None and (type(count) is not int or count < 0):
            raise StorageSchemaError('notices_found must be a nonnegative integer or null')
    return data


def _write_and_sync(handle: TextIO, text: str) -> None:
    handle.write(text)
    handle.flush()
    os.fsync(handle.fileno())


def _atomic_json(path: Path, data: object) -> None:
    # Serialize before touching the existing file or creating a directory.
    try:
        text = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n'
        text.encode('utf-8')  # reject lone surrogates before creating a temp file
    except (TypeError, ValueError, RecursionError, UnicodeError) as error:
        raise StorageSchemaError('data is not serializable standard JSON') from error
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode='w', encoding='utf-8', newline='\n', dir=path.parent,
            prefix=f'.{path.name}.', suffix='.tmp', delete=False,
        ) as handle:
            temporary = Path(handle.name)
            _write_and_sync(handle, text)
        # Commit point: file is closed before replacement (also required on Windows).
        os.replace(temporary, path)
    except OSError as error:
        raise StorageIOError(f'{path}: atomic save failed') from error
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                # A cleanup failure must not hide the original write error or
                # report a failed save after the commit already succeeded.
                pass


class JsonStorage:
    """UTF-8 snapshots at data/notices.json and data/scraper_status.json.

    Missing files read as []/{} without writing anything. Damaged files raise
    StorageError; no implicit reset. Saves preserve Notice list ordering, sort
    object keys and use two-space indentation/LF/trailing newline. Single writer
    expected: atomic replace is not a concurrent merge or a power-loss guarantee.
    """

    def __init__(self, data_dir: str | Path | None = None):
        root = Path(data_dir) if data_dir is not None else Path(__file__).resolve().parents[2] / 'data'
        self.data_dir = root.resolve()
        self.notices_path = self.data_dir / 'notices.json'
        self.scraper_status_path = self.data_dir / 'scraper_status.json'

    def load_notices(self) -> list[Notice]:
        return _notice_records(_read_json(self.notices_path, []))

    def save_notices(self, notices: list[Notice]) -> None:
        if not isinstance(notices, list) or any(not isinstance(n, Notice) for n in notices):
            raise StorageSchemaError('save_notices requires list[Notice]')
        records = [notice.to_dict() for notice in notices]
        _notice_records(records)  # same strict contract on save and load
        _atomic_json(self.notices_path, records)

    def load_scraper_status(self) -> dict:
        return _status_records(_read_json(self.scraper_status_path, {}))

    def save_scraper_status(self, statuses: dict) -> None:
        _status_records(statuses)
        _atomic_json(self.scraper_status_path, statuses)
