"""Patent-firm participation eligibility, versioned cache, isolated failures."""

from __future__ import annotations

import logging
import time
from dataclasses import replace
from datetime import datetime, timezone

from src.ai.gemini import GeminiClient, GeminiError, notice_payload, parse_decision
from src.core.models import GeminiResult, GeminiStatus, Notice, NoticeStatus
from src.core.eligibility import ANALYSIS_POLICY, current_analysis


def _complete_success(result: GeminiResult, content_hash: str) -> bool:
    return (
        result.status == GeminiStatus.SUCCESS and result.analysis_policy == ANALYSIS_POLICY
        and result.analyzed_content_hash == content_hash
        and type(result.relevant) is bool and result.category is not None
        and result.participation_type is not None and result.reason is not None
        and result.keywords is not None
    )


class RelevanceAnalyzer:
    """One instance per central analysis session; cache key is (notice_id, hash).

    Persisted complete SUCCESS is reusable across instances. In-memory attempts
    (including failures) are memoized so repeated inputs do not spend more calls.
    Default callers preserve the original EXISTING no-call contract. Central
    orchestration opts into retrying PENDING/NOT_ANALYZED with a bounded budget
    and a session pause on HTTP 429. No immediate retry/backoff loops here.
    """
    def __init__(self, client: GeminiClient, *, clock=None, logger=None,
                 retry_existing=False, max_calls=None, stop_on_rate_limit=False,
                 min_call_interval=0, sleep=time.sleep, monotonic=time.monotonic):
        if max_calls is not None and (type(max_calls) is not int or max_calls < 1):
            raise ValueError('max_calls must be a positive integer')
        self.client = client
        self.retry_existing = retry_existing
        self.max_calls = max_calls
        self.stop_on_rate_limit = stop_on_rate_limit
        self.calls = 0
        self.min_call_interval = min_call_interval
        self._sleep, self._monotonic, self._last_call = sleep, monotonic, None
        self.paused = False
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
        if notice.status == NoticeStatus.EXISTING and not (
            self.retry_existing and not current_analysis(notice)
        ):
            # Preserve previous results exactly; no API call even if historical
            # data lacks a complete M08 analysis. Unknown work remains pending.
            if notice.gemini.status == GeminiStatus.NOT_ANALYZED:
                return replace(notice, gemini=replace(notice.gemini, status=GeminiStatus.PENDING))
            return notice
        if self.paused or (self.max_calls is not None and self.calls >= self.max_calls):
            self.errors[notice.notice_id] = 'RATE_LIMIT_DEFERRED' if self.paused else 'BUDGET_DEFERRED'
            result = replace(notice.gemini, status=GeminiStatus.PENDING)
            self._cache[key] = result
            return replace(notice, gemini=result)
        try:
            if self._last_call is not None and self.min_call_interval:
                delay = self.min_call_interval - (self._monotonic() - self._last_call)
                if delay > 0:
                    self._sleep(delay)
            self._last_call = self._monotonic()
            now = self.clock()
            if now.tzinfo is None or now.utcoffset() is None:
                raise ValueError('clock must be timezone aware')
            self.calls += 1
            decision = parse_decision(self.client.generate(notice_payload(notice)))
            result = GeminiResult(
                status=GeminiStatus.SUCCESS, relevant=decision['relevant'],
                category=decision['category'], participation_type=decision['participation_type'],
                reason=decision['reason'], keywords=decision['keywords'],
                analyzed_at=now.isoformat(), analyzed_content_hash=notice.content_hash,
                analysis_policy=ANALYSIS_POLICY,
            )
            self.errors.pop(notice.notice_id, None)
        except Exception as error:
            if isinstance(error, GeminiError):
                code, pending = error.code, error.retryable
                if self.stop_on_rate_limit and error.http_status == 429:
                    self.paused = True
            elif isinstance(error, (TimeoutError, ConnectionError)):
                code, pending = 'NETWORK_OR_TIMEOUT', True
            else:
                code, pending = 'ANALYSIS_ERROR', False
            # Keep last successful judgment/hash/time as history, with a non-
            # SUCCESS state so a later feed cannot treat it as current success.
            result = replace(notice.gemini, status=GeminiStatus.PENDING if pending else GeminiStatus.FAILED)
            self.errors[notice.notice_id] = code
            self.logger.warning('gemini_analysis_failed code=%s http_status=%s', code,
                                error.http_status if isinstance(error, GeminiError) else None)
        self._cache[key] = result
        return replace(notice, gemini=result)

    def analyze_batch(self, notices) -> list[Notice]:
        return [self.analyze(notice) for notice in notices]
