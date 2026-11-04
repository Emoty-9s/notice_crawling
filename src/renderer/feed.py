"""M09 self-contained public JSON projection, with no API or pipeline calls."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from src.core.models import Notice
from src.core.normalizer import clean_content_text
from src.core.storage import _atomic_json
from src.core.eligibility import PUBLIC_SCHEMA_VERSION, eligible_active_notices
from src.core.public_text import mask_contacts, public_hash
from src.ai.prefilter import Prefilter


SCHEMA_VERSION = PUBLIC_SCHEMA_VERSION
SUMMARY_LIMIT = 300
PUBLIC_DIR = Path(__file__).resolve().parents[2] / 'public'


class FeedInputError(ValueError):
    """Invalid caller input or conflicting public records; no silent overwrite."""


def _timestamp(value: str) -> str:
    if not isinstance(value, str):
        raise FeedInputError('generated_at must be a timezone-aware ISO datetime')
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError('missing timezone')
        return parsed.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    except (ValueError, OverflowError):
        raise FeedInputError('generated_at must be a timezone-aware ISO datetime') from None


def _publishable(notice: Notice) -> bool:
    return bool(notice.content_hash)


def _public_notice(notice: Notice) -> dict:
    for name in ('notice_id', 'source_id', 'institution', 'title', 'url', 'first_seen_at', 'updated_at'):
        if not getattr(notice, name).strip():
            raise FeedInputError(f'public notice requires nonempty {name}')
    text = mask_contacts(clean_content_text(notice.content_text))
    summary = text if len(text) <= SUMMARY_LIMIT else text[:SUMMARY_LIMIT - 1].rstrip() + '…'
    status,reason = Prefilter().classify(notice)
    record = {
        'notice_id': notice.notice_id,
        'source_id': notice.source_id,
        'institution': notice.institution,
        'title': mask_contacts(notice.title),
        'published_at': notice.published_at,
        'apply_start': notice.apply_start,
        'apply_end': notice.apply_end,
        'url': notice.url,
        'summary': summary,
        'content_text': text,
        'prefilter_status': status,
        'prefilter_reason_code': reason,
        'prefilter_policy_version': Prefilter().version,
        'content_hash': notice.content_hash,
        'first_seen_at': notice.first_seen_at,
        'updated_at': notice.updated_at,
    }
    record['public_content_hash'] = public_hash(record)
    return record


def build_feed(notices: Iterable[Notice], *, generated_at: str) -> dict:
    """Pure projection sorted by (source_id, notice_id); timestamp is required.

    Identical public duplicates collapse; conflicting records sharing an ID
    raise FeedInputError rather than picking an input-order-dependent winner.
    Optional dates stay null. Summary is a normalized excerpt, not an AI summary.
    """
    timestamp = _timestamp(generated_at)
    records = {}
    values = list(notices)
    if any(not isinstance(n, Notice) for n in values):
        raise FeedInputError('build_feed requires an iterable of Notice')
    # Expiration is a user-local view: keep rows available for date overrides,
    # closed-notice browsing and restoration without changing the v3 schema.
    for notice in eligible_active_notices(values, today=datetime.fromisoformat(timestamp), include_expired=True):
        if not isinstance(notice, Notice):
            raise FeedInputError('build_feed requires an iterable of Notice')
        if not _publishable(notice):
            continue
        record = _public_notice(notice)
        record['is_new'] = (notice.status == 'NEW' and _timestamp(notice.first_seen_at) == timestamp)
        if notice.notice_id in records and records[notice.notice_id] != record:
            raise FeedInputError('conflicting public records for the same notice_id')
        records[notice.notice_id] = record
    return {
        'schema_version': SCHEMA_VERSION,
        'generated_at': timestamp,
        'notices': sorted(records.values(), key=lambda record: (record['source_id'], record['notice_id'])),
    }


def write_feed(
    notices: Iterable[Notice], *, generated_at: str, output_dir: str | Path | None = None,
) -> tuple[Path, Path]:
    """Explicitly write notices.json then metadata.json; return their paths.

    Reuse M06's UTF-8/sorted-key/indent/LF atomic JSON primitive. Each file is
    atomic, not a two-file transaction. An I/O failure is raised to the caller;
    no collection, storage loading, Gemini analysis or retries occur here.
    """
    feed = build_feed(notices, generated_at=generated_at)
    metadata = {
        'schema_version': SCHEMA_VERSION,
        'generated_at': feed['generated_at'],
        'notice_count': len(feed['notices']),
    }
    root = Path(output_dir) if output_dir is not None else PUBLIC_DIR
    notices_path, metadata_path = root / 'notices.json', root / 'metadata.json'
    _atomic_json(notices_path, feed)
    _atomic_json(metadata_path, metadata)
    return notices_path, metadata_path
