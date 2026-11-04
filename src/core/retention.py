"""Shared deadline retention. Unknown deadlines never imply expiration."""
from datetime import date, datetime, timedelta, timezone
import re


KST = timezone(timedelta(hours=9))
RETENTION_DAYS = 90


def retention_date(now=None):
    now = datetime.now(KST) if now is None else now
    if isinstance(now, datetime):
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError('retention clock must be timezone-aware')
        return now.astimezone(KST).date()
    if isinstance(now, date):
        return now
    raise ValueError('invalid retention clock')


def expired(apply_end, *, today=None):
    """Keep through deadline + 90 calendar days (inclusive), in Korea time.

    Only unambiguous ISO dates/datetimes are accepted. Missing, invalid and
    ongoing/textual deadlines are retained rather than guessed from creation.
    """
    if not isinstance(apply_end, str):
        return False
    value = apply_end.strip()
    try:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            deadline = date.fromisoformat(value)
        elif re.match(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}', value):
            parsed = datetime.fromisoformat(value)
            deadline = parsed.astimezone(KST).date() if parsed.tzinfo else parsed.date()
        else:
            return False
    except ValueError:
        return False
    return (retention_date(today) - deadline).days > RETENTION_DAYS
