"""Shared data contract (M02), without scraping, normalization or API calls.

Dates remain strings: callers should supply ISO dates (YYYY-MM-DD) or ISO
timestamps with an explicit offset (UTC may use Z). Unknown optional values
are None. Parsing/normalizing source dates belongs to M03. Required identity,
hash and observation timestamps must be supplied; nothing is generated here.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Protocol, Self


class NoticeStatus(StrEnum):
    NEW = "NEW"
    UPDATED = "UPDATED"
    EXISTING = "EXISTING"


class GeminiStatus(StrEnum):
    NOT_ANALYZED = "NOT_ANALYZED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PENDING = "PENDING"


class NoticeIdGenerator(Protocol):
    """Callable signature only; stable identity implementation belongs to M03."""

    def __call__(
        self, *, source_id: str, title: str, url: str,
        source_notice_id: str | None = None, notice_number: str | None = None,
    ) -> str: ...


class ContentHashGenerator(Protocol):
    """Callable signature only; normalization/hash algorithm belongs to M03."""

    def __call__(self, *, content_text: str) -> str: ...


def _text(name: str, value: object, *, optional: bool = False) -> None:
    if optional and value is None:
        return
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string" + (" or None" if optional else ""))
    if optional and not value.strip():
        raise ValueError(f"{name}: use None for an unknown optional value")


class _JsonModel:
    def to_dict(self) -> dict:
        raise NotImplementedError

    def to_json(self) -> str:
        """Return UTF-8-friendly JSON; non-finite numbers are never emitted."""
        return json.dumps(self.to_dict(), ensure_ascii=False, allow_nan=False)

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        if not isinstance(data, dict):
            raise TypeError(f"{cls.__name__} requires a JSON object")
        return cls(**data)

    @classmethod
    def from_json(cls, text: str) -> Self:
        return cls.from_dict(json.loads(text))


@dataclass(frozen=True, kw_only=True)
class GeminiResult(_JsonModel):
    """Stored analysis data, not an API client or relevance policy.

    score is retained for legacy storage compatibility; M08 does not use it.
    Historical results may lack new outputs, so the M08 analyzer validates
    a complete current success separately from this backward-compatible model.
    """

    status: GeminiStatus = GeminiStatus.NOT_ANALYZED
    relevant: bool | None = None
    score: int | float | None = None
    reason: str | None = None
    category: str | None = None
    analyzed_at: str | None = None
    analyzed_content_hash: str | None = None
    participation_type: str | None = None
    keywords: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", GeminiStatus(self.status))
        if self.relevant is not None and type(self.relevant) is not bool:
            raise TypeError("relevant must be a boolean or None")
        if self.score is not None:
            if type(self.score) not in (int, float):
                raise TypeError("score must be a number or None")
            if isinstance(self.score, float) and not math.isfinite(self.score):
                raise ValueError("score must be finite")
        for name in ("reason", "category", "analyzed_at", "analyzed_content_hash", "participation_type"):
            _text(name, getattr(self, name), optional=True)
        if self.keywords is not None:
            if not isinstance(self.keywords, (list, tuple)):
                raise TypeError("keywords must be a sequence of strings or None")
            for keyword in self.keywords:
                _text("keyword", keyword, optional=True)
                if keyword is None:
                    raise TypeError("keyword must be a string")
            object.__setattr__(self, "keywords", tuple(self.keywords))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["status"] = self.status.value
        data["keywords"] = list(self.keywords) if self.keywords is not None else None
        return data


@dataclass(frozen=True, kw_only=True)
class Notice(_JsonModel):
    """Common scraper output; required fields are caller-supplied strings.

    Empty content_text is permitted for an unavailable web body. Optional
    text uses None rather than an empty string. No ID/hash calculation,
    automatic clock, status transition or date normalization occurs here.
    """

    notice_id: str
    source_id: str
    institution: str
    title: str
    url: str
    content_text: str
    content_hash: str
    first_seen_at: str
    last_seen_at: str
    updated_at: str
    category: str | None = None
    published_at: str | None = None
    apply_start: str | None = None
    apply_end: str | None = None
    status: NoticeStatus = NoticeStatus.NEW
    gemini: GeminiResult = field(default_factory=GeminiResult)

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", NoticeStatus(self.status))
        for name in (
            "notice_id", "source_id", "institution", "title", "url",
            "content_text", "content_hash", "first_seen_at", "last_seen_at",
            "updated_at",
        ):
            _text(name, getattr(self, name))
        for name in ("category", "published_at", "apply_start", "apply_end"):
            _text(name, getattr(self, name), optional=True)
        if not isinstance(self.gemini, GeminiResult):
            raise TypeError("gemini must be a GeminiResult")

    def to_dict(self) -> dict:
        data = asdict(self)
        data["status"] = self.status.value
        data["gemini"] = self.gemini.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        if not isinstance(data, dict):
            raise TypeError("Notice requires a JSON object")
        values = dict(data)
        if "gemini" in values:
            values["gemini"] = GeminiResult.from_dict(values["gemini"])
        return cls(**values)
