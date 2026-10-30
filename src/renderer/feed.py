"""M09 self-contained public JSON projection, with no API or pipeline calls."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from src.core.models import GeminiStatus, Notice
from src.core.normalizer import clean_content_text
from src.core.storage import _atomic_json


SCHEMA_VERSION = 1
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
    result = notice.gemini
    # M08 keeps historical results, including legacy successes. Publish only a
    # complete success for this body, not a stale or incomplete old judgment.
    return (
        result.status == GeminiStatus.SUCCESS and result.relevant is True
        and bool(notice.content_hash) and result.analyzed_content_hash == notice.content_hash
        and result.category is not None and result.participation_type is not None
        and result.reason is not None and result.keywords is not None
    )


def _public_notice(notice: Notice) -> dict:
    for name in ('notice_id', 'source_id', 'institution', 'title', 'url', 'first_seen_at', 'updated_at'):
        if not getattr(notice, name).strip():
            raise FeedInputError(f'public notice requires nonempty {name}')
    text = clean_content_text(notice.content_text)
    summary = text if len(text) <= SUMMARY_LIMIT else text[:SUMMARY_LIMIT - 1].rstrip() + '…'
    result = notice.gemini
    # Explicit allowlist: never distribute the internal model or full body.
    return {
        'notice_id': notice.notice_id,
        'source_id': notice.source_id,
        'institution': notice.institution,
        'title': notice.title,
        'category': result.category,
        'participation_type': result.participation_type,
        'published_at': notice.published_at,
        'apply_start': notice.apply_start,
        'apply_end': notice.apply_end,
        'url': notice.url,
        'summary': summary,
        'keywords': list(result.keywords),
        'relevance_reason': result.reason,
        'first_seen_at': notice.first_seen_at,
        'updated_at': notice.updated_at,
    }


def build_feed(notices: Iterable[Notice], *, generated_at: str) -> dict:
    """Pure projection sorted by (source_id, notice_id); timestamp is required.

    Identical public duplicates collapse; conflicting records sharing an ID
    raise FeedInputError rather than picking an input-order-dependent winner.
    Optional dates stay null. Summary is a normalized excerpt, not an AI summary.
    """
    timestamp = _timestamp(generated_at)
    records = {}
    for notice in notices:
        if not isinstance(notice, Notice):
            raise FeedInputError('build_feed requires an iterable of Notice')
        if not _publishable(notice):
            continue
        record = _public_notice(notice)
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
