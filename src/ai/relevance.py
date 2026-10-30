"""Central industry relevance only: hash cache and per-Notice failure isolation."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timezone

from src.ai.gemini import GeminiClient, GeminiError, notice_payload, parse_decision
from src.core.models import GeminiResult, GeminiStatus, Notice, NoticeStatus


def _complete_success(result: GeminiResult, content_hash: str) -> bool:
    return (
        result.status == GeminiStatus.SUCCESS and result.analyzed_content_hash == content_hash
        and type(result.relevant) is bool and result.category is not None
        and result.participation_type is not None and result.reason is not None
        and result.keywords is not None
    )


class RelevanceAnalyzer:
    """One instance per central analysis session; cache key is (notice_id, hash).

    Persisted complete SUCCESS is reusable across instances. In-memory attempts
    (including failures) are memoized so repeated inputs do not spend more calls.
    No storage/feed/orchestration or per-company context. Failed/pending attempts
    can be retried by a future NEW/UPDATED run with a new analyzer; EXISTING never
    invokes the API. No automatic retry/backoff loops here.
    """
    def __init__(self, client: GeminiClient, *, clock=None, logger=None):
        self.client = client
        self.clock = clock if clock is not None else lambda: datetime.now(timezone.utc)
        self.logger = logger if logger is not None else logging.getLogger(__name__)
        self._cache: dict[tuple[str, str], GeminiResult] = {}
        self.errors: dict[str, str] = {}

    def analyze(self, notice: Notice) -> Notice:
        if not isinstance(notice, Notice):
            raise TypeError('analyze requires a Notice')
        key = (notice.notice_id, notice.content_hash)
        if _complete_success(notice.gemini, notice.content_hash):
            self._cache[key] = notice.gemini
            self.errors.pop(notice.notice_id, None)
            return notice
        if key in self._cache:
            return replace(notice, gemini=self._cache[key])
        if notice.status == NoticeStatus.EXISTING:
            # Preserve previous results exactly; no API call even if historical
            # data lacks a complete M08 analysis. Unknown work remains pending.
            if notice.gemini.status == GeminiStatus.NOT_ANALYZED:
                return replace(notice, gemini=replace(notice.gemini, status=GeminiStatus.PENDING))
            return notice
        try:
            now = self.clock()
            if now.tzinfo is None or now.utcoffset() is None:
                raise ValueError('clock must be timezone aware')
            decision = parse_decision(self.client.generate(notice_payload(notice)))
            result = GeminiResult(
                status=GeminiStatus.SUCCESS, relevant=decision['relevant'],
                category=decision['category'], participation_type=decision['participation_type'],
                reason=decision['reason'], keywords=decision['keywords'],
                analyzed_at=now.isoformat(), analyzed_content_hash=notice.content_hash,
            )
            self.errors.pop(notice.notice_id, None)
        except Exception as error:
            if isinstance(error, GeminiError):
                code, pending = error.code, error.retryable
            elif isinstance(error, (TimeoutError, ConnectionError)):
                code, pending = 'NETWORK_OR_TIMEOUT', True
            else:
                code, pending = 'ANALYSIS_ERROR', False
            # Keep last successful judgment/hash/time as history, with a non-
            # SUCCESS state so a later feed cannot treat it as current success.
            result = replace(notice.gemini, status=GeminiStatus.PENDING if pending else GeminiStatus.FAILED)
            self.errors[notice.notice_id] = code
            self.logger.warning('gemini_analysis_failed code=%s', code)
        self._cache[key] = result
        return replace(notice, gemini=result)

    def analyze_batch(self, notices) -> list[Notice]:
        return [self.analyze(notice) for notice in notices]
