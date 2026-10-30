"""M07 pure Notice comparison, change reporting and batch deduplication.

Caller supplies one ISO observation timestamp. No clock, storage, network,
Gemini policy/calls or scraper behavior is invoked here.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime

from src.core.models import Notice, NoticeStatus
from src.core.normalizer import (
    clean_content_text, normalize_date, normalize_institution,
    normalize_url, normalize_whitespace,
)


TRACKED_FIELDS = (
    'content_hash', 'content_text', 'title', 'institution', 'category',
    'published_at', 'apply_start', 'apply_end', 'url',
)


class DiffInputError(ValueError):
    """Invalid comparison input, timestamp or mismatched source/identity."""


class DiffConflictError(DiffInputError):
    """Conflicting current duplicates or ambiguous duplicate stored identities."""


@dataclass(frozen=True)
class FieldChange:
    field: str
    before: str | None
    after: str | None


@dataclass(frozen=True)
class NoticeDiff:
    notice: Notice
    changes: tuple[FieldChange, ...] = ()

    @property
    def changed_fields(self) -> tuple[str, ...]:
        return tuple(change.field for change in self.changes)

    @property
    def content_changed(self) -> bool:
        """Observed body/hash difference, not a decision to invoke Gemini."""
        return any(field in self.changed_fields for field in ('content_hash', 'content_text'))


@dataclass(frozen=True)
class DuplicateNotice:
    notice_id: str
    input_indexes: tuple[int, ...]  # zero-based positions in the collected batch


@dataclass(frozen=True)
class BatchDiff:
    results: tuple[NoticeDiff, ...]
    duplicates: tuple[DuplicateNotice, ...] = ()

    @property
    def notices(self) -> list[Notice]:
        """Observed unique records only; unseen stored records are not deleted."""
        return [result.notice for result in self.results]


def _timestamp(value: str) -> str:
    if not isinstance(value, str) or 'T' not in value:
        raise DiffInputError('observed_at must be an ISO datetime with timezone')
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise DiffInputError('invalid observed_at') from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DiffInputError('observed_at must include a timezone')
    return value


def _check_notice(notice: Notice) -> None:
    if not isinstance(notice, Notice):
        raise DiffInputError('comparison inputs must contain Notice instances')
    if not notice.notice_id.strip() or not notice.source_id.strip():
        raise DiffInputError('notice_id and source_id must not be empty')


def _semantic(notice: Notice) -> tuple:
    values = []
    for name in TRACKED_FIELDS:
        value = getattr(notice, name)
        if value is not None:
            if name == 'url':
                value = normalize_url(value)
            elif name == 'institution':
                value = normalize_institution(value)
            elif name == 'content_text':
                value = clean_content_text(value)
            elif name in ('published_at', 'apply_start', 'apply_end'):
                # Unknown date strings stay distinguishable; never collapse
                # all unsupported values into the same None.
                value = normalize_date(value) or normalize_whitespace(value)
            elif name != 'content_hash':
                value = normalize_whitespace(value)
        values.append(value)
    return tuple(values)


def _signature(notice: Notice) -> tuple:
    try:
        return _semantic(notice)
    except (TypeError, ValueError) as error:
        raise DiffInputError('invalid tracked Notice values') from error


def _compare(collected: Notice, previous: Notice | None, observed_at: str) -> NoticeDiff:
    if previous is None:
        # Keep a caller-supplied Gemini result, if any; never perform analysis.
        return NoticeDiff(replace(
            collected, status=NoticeStatus.NEW, first_seen_at=observed_at,
            last_seen_at=observed_at, updated_at=observed_at,
        ))
    if collected.notice_id != previous.notice_id or collected.source_id != previous.source_id:
        raise DiffInputError('cannot compare different notice/source identities')
    before, after = _signature(previous), _signature(collected)
    changes = tuple(
        FieldChange(name, getattr(previous, name), getattr(collected, name))
        for name, old, new in zip(TRACKED_FIELDS, before, after) if old != new
    )
    if not changes:
        # Preserve the prior representation too: whitespace/canonical variants
        # do not churn stored content or its modification timestamp.
        return NoticeDiff(replace(previous, status=NoticeStatus.EXISTING, last_seen_at=observed_at))
    return NoticeDiff(replace(
        collected, status=NoticeStatus.UPDATED, first_seen_at=previous.first_seen_at,
        last_seen_at=observed_at, updated_at=observed_at, gemini=previous.gemini,
    ), changes)


def compare_notice(
    collected: Notice, previous: Notice | None = None, *, observed_at: str,
) -> NoticeDiff:
    """Compare one normalized Notice; inputs remain immutable.

    NEW sets all observation/modification timestamps to observed_at. Known
    records keep first_seen_at/Gemini; EXISTING also keeps updated_at. Status,
    observation timestamps and Gemini are never meaningful-change criteria.
    """
    stamp = _timestamp(observed_at)
    _check_notice(collected)
    _signature(collected)
    if previous is not None:
        _check_notice(previous)
    return _compare(collected, previous, stamp)


def compare_batch(
    collected: Iterable[Notice], previous: Iterable[Notice], *, observed_at: str,
) -> BatchDiff:
    """Compare a batch once against stored records, not against earlier results.

    Preserve first-occurrence order. Semantically identical current duplicates
    (including identical Gemini payload) collapse to one and report indexes.
    Conflicting duplicates raise before returning anything; no arbitrary winner
    or mixed snapshot. Duplicate IDs in stored input also require caller repair.

    Result contains observed unique IDs only. Retaining/merging unseen stored
    records and saving snapshots is later orchestration, not this function.
    """
    stamp = _timestamp(observed_at)
    stored = {}
    for record in previous:
        _check_notice(record)
        if record.notice_id in stored:
            raise DiffConflictError('duplicate notice_id in stored records')
        stored[record.notice_id] = record
    current = {}
    signatures = {}
    indexes: dict[str, list[int]] = {}
    for index, record in enumerate(collected):
        _check_notice(record)
        signature = (record.source_id, _signature(record), record.gemini)
        notice_id = record.notice_id
        if notice_id in current:
            if signature != signatures[notice_id]:
                raise DiffConflictError('conflicting duplicate notice_id in collected records')
            indexes[notice_id].append(index)
        else:
            current[notice_id] = record
            signatures[notice_id] = signature
            indexes[notice_id] = [index]
    return BatchDiff(
        tuple(_compare(record, stored.get(notice_id), stamp) for notice_id, record in current.items()),
        tuple(DuplicateNotice(notice_id, tuple(positions))
              for notice_id, positions in indexes.items() if len(positions) > 1),
    )
