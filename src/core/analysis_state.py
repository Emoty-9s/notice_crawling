"""Durable per-notice work state, embedded in the atomic history snapshot."""
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass(frozen=True, kw_only=True)
class AnalysisState:
    content_hash: str | None = None
    analysis_policy: str | None = None
    result_schema_fingerprint: str | None = None
    target_schema_fingerprint: str | None = None
    prefilter_policy_version: str | None = None
    prefilter_content_hash: str | None = None
    prefilter_status: str | None = None
    prefilter_reason_code: str | None = None
    evaluated_at: str | None = None
    analysis_status: str = 'PENDING'
    attempts: int = 0
    last_attempt_at: str | None = None
    next_retry_at: str | None = None
    lease_until: str | None = None
    last_error_code: str | None = None
    fallback_size: int = 10
    # Prior successful decisions are retained when a new policy/body succeeds.
    previous_results: tuple = ()

    def __post_init__(self):
        if self.analysis_status not in {'PENDING','IN_PROGRESS','RETRY_WAIT','SUCCESS','PERMANENT_FAILURE','STALE_POLICY'}:
            raise ValueError('INVALID_ANALYSIS_STATUS')
        if self.prefilter_status not in {None,'CANDIDATE','REVIEW','CLEARLY_UNRELATED'}:
            raise ValueError('INVALID_PREFILTER_STATUS')
        for name, value in asdict(self).items():
            if name in {'attempts','fallback_size','previous_results'}:
                continue
            if value is not None and (not isinstance(value,str) or not value.strip()):
                raise ValueError('INVALID_ANALYSIS_FIELD')
        if type(self.attempts) is not int or self.attempts < 0:
            raise ValueError('INVALID_ATTEMPTS')
        if type(self.fallback_size) is not int or not 1 <= self.fallback_size <= 10:
            raise ValueError('INVALID_FALLBACK_SIZE')
        for name in ('evaluated_at','last_attempt_at','next_retry_at','lease_until'):
            if getattr(self,name) is not None:
                stamp = datetime.fromisoformat(getattr(self,name))
                if stamp.tzinfo is None or stamp.utcoffset() is None:
                    raise ValueError('INVALID_ANALYSIS_TIMESTAMP')
        from .models import GeminiResult
        results = tuple(v if isinstance(v,GeminiResult) else GeminiResult.from_dict(v) for v in self.previous_results)
        object.__setattr__(self,'previous_results',results)

    def to_dict(self):
        return {**asdict(self),'previous_results':[v.to_dict() for v in self.previous_results]}
