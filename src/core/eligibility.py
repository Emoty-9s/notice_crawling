"""Patent-firm participation policy and deterministic Korean deadline rules.

Storage is observation history; these rules only select work queues and views.
"""
import re
import hashlib
import json
from pathlib import Path
from functools import lru_cache
from datetime import date, datetime
from .retention import KST, retention_date

ANALYSIS_POLICY = 'patent-firm-participation-v2'
PUBLIC_SCHEMA_VERSION = 2
LEGACY_SCHEMA_FINGERPRINT = '75a521c34b60419a509b634441ab77350872cc3b118658de7a831ffe7a6fdef3'


@lru_cache(maxsize=1)
def analysis_schema_fingerprint():
    # Only central Notice analysis uses this. Local feed consumers import date
    # helpers without loading Gemini policy files (including in frozen builds).
    schema = json.loads((Path(__file__).resolve().parents[2]/'config/relevance_policy.yaml').read_text(encoding='utf-8'))['output_schema']
    return hashlib.sha256(json.dumps(schema,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def deadline_date(value):
    if not isinstance(value, str):
        return None
    try:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value.strip()):
            return date.fromisoformat(value.strip())
        if re.match(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}', value.strip()):
            stamp = datetime.fromisoformat(value.strip())
            return stamp.astimezone(KST).date() if stamp.tzinfo else stamp.date()
    except ValueError:
        pass
    return None


def deadline_state(apply_end, *, today=None, title='', content=''):
    end = deadline_date(apply_end)
    if end is not None:
        return 'EXPIRED' if end < retention_date(today) else 'ACTIVE'
    # Only standalone, explicit closure statements. No prose substring guess
    # (e.g. "접수 마감 후" or "미마감" is not evidence of a closed notice).
    statements = re.split(r'[\n\r]|[.!。]', content)
    closed = r'\s*(?:\[)?(?:모집|접수|신청|공고)\s*(?:종료|마감)(?:\])?\s*'
    if any(re.fullmatch(closed, text) for text in [title, *statements]):
        return 'EXPIRED'
    return 'UNKNOWN'


def current_analysis(notice):
    result = notice.gemini
    return (result.status == 'SUCCESS' and result.analysis_policy == ANALYSIS_POLICY
            and (notice.analysis.result_schema_fingerprint or LEGACY_SCHEMA_FINGERPRINT) == analysis_schema_fingerprint()
            and result.analyzed_content_hash == notice.content_hash
            and type(result.relevant) is bool
            and all(getattr(result, field) is not None for field in
                    ('category', 'participation_type', 'reason', 'keywords')))


def eligible_active_notices(notices, *, today=None):
    return [n for n in notices if current_analysis(n) and n.gemini.relevant is True
            and deadline_state(n.apply_end, today=today, title=n.title, content=n.content_text) != 'EXPIRED']
