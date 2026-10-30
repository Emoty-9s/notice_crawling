"""M04 scraper lifecycle and injectable standard-library HTTP support."""

from __future__ import annotations

import logging
import math
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Generic, Protocol, TypeVar
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.core.models import Notice


Item = TypeVar("Item")
Parsed = TypeVar("Parsed")
Result = TypeVar("Result")


@dataclass(frozen=True, kw_only=True)
class HttpSettings:
    timeout_seconds: float = 15.0
    max_retries: int = 2
    backoff_seconds: float = 0.5
    user_agent: str = "NoticeMonitor/0.1"

    def __post_init__(self) -> None:
        for name in ("timeout_seconds", "backoff_seconds"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number")
        if self.timeout_seconds <= 0 or self.backoff_seconds < 0:
            raise ValueError("timeout must be positive and backoff nonnegative")
        if type(self.max_retries) is not int or not 0 <= self.max_retries <= 10:
            raise ValueError("max_retries must be an integer between 0 and 10")
        if not isinstance(self.user_agent, str) or not self.user_agent.strip():
            raise ValueError("user_agent must be a nonempty string")
        if any(ord(c) < 32 or ord(c) == 127 for c in self.user_agent):
            raise ValueError("user_agent must not contain control characters")


class HttpTransport(Protocol):
    def get(self, url: str, *, timeout: float, headers: Mapping[str, str]) -> str: ...


class UrllibTransport:
    """Generic GET adapter. Constructing it does not perform network I/O."""

    def get(self, url: str, *, timeout: float, headers: Mapping[str, str]) -> str:
        request = Request(url, headers=dict(headers), method="GET")
        with urlopen(request, timeout=timeout) as response:
            encoding = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(encoding)


class ScraperError(Exception):
    """Source/phase boundary error; original exception is retained as __cause__."""

    def __init__(self, source_id: str, stage: str, cause: Exception) -> None:
        self.source_id = source_id
        self.stage = stage
        self.error_type = type(cause).__name__
        # Avoid putting response bodies, credentials or query strings in logs.
        super().__init__(f"{source_id}: {stage} failed ({self.error_type})")


def validate_notices(notices: object, source_id: str) -> None:
    """Validate before publishing a source's results (including overridden run)."""
    if not isinstance(notices, list):
        raise TypeError("scraper result must be list[Notice]")
    for notice in notices:
        if not isinstance(notice, Notice):
            raise TypeError("scraper result must contain only Notice instances")
        if notice.source_id != source_id:
            raise ValueError("Notice.source_id must match the scraper source_id")


class BaseScraper(ABC, Generic[Item, Parsed]):
    """Template method: list fetch/parse -> detail fetch/parse -> normalize.

    A failed item aborts this source's run; no partial source result is returned.
    Registry isolates that failure from other sources. Subclasses should use
    request_text for HTTP in both fetch methods, so timeout/retry/UA apply.
    normalize must return a Notice using M02/M03 contracts, with observation
    timestamps supplied by the caller/subclass. No storage or diff here.
    """

    def __init__(
        self, site_config: Mapping[str, Any], *,
        transport: HttpTransport | None = None,
        http_settings: HttpSettings | None = None,
        sleep: Callable[[float], None] = time.sleep,
        logger: logging.Logger | None = None,
    ) -> None:
        snapshot = deepcopy(dict(site_config))
        source_id = snapshot.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("site_config.source_id must be a nonempty string")
        if type(snapshot.get("enabled", False)) is not bool:
            raise ValueError("site_config.enabled must be a boolean")
        self.config = MappingProxyType(snapshot)
        self.source_id = source_id
        self.enabled = snapshot.get("enabled", False)
        self.http_settings = (
            http_settings if http_settings is not None
            else HttpSettings(**snapshot.get("http", {}))
        )
        self.transport = transport if transport is not None else UrllibTransport()
        self._sleep = sleep
        self.logger = logger if logger is not None else logging.getLogger(__name__)

    def request_text(self, url: str) -> str:
        """Bounded GET retries: transient network errors, 429 and selected 5xx.

        max_retries is additional attempts after the first. Exponential delay
        is capped at 30s per retry. No parse/normalization retries or access
        control bypass. The timeout applies to transport socket operations,
        not an absolute deadline for the entire scraper run.
        """
        options = self.http_settings
        for attempt in range(options.max_retries + 1):
            try:
                text = self.transport.get(
                    url, timeout=options.timeout_seconds,
                    headers={"User-Agent": options.user_agent},
                )
                if not isinstance(text, str):
                    raise TypeError("transport.get must return text")
                return text
            except HTTPError as error:
                if error.code not in {429, 500, 502, 503, 504}:
                    raise
                if attempt == options.max_retries:
                    raise
            except (URLError, TimeoutError, ConnectionError):
                if attempt == options.max_retries:
                    raise
            self.logger.warning(
                "scraper_retry source_id=%s attempt=%d", self.source_id, attempt + 1,
            )
            self._sleep(min(30.0, options.backoff_seconds * (2 ** attempt)))
        raise AssertionError("unreachable retry state")

    def fetch_list(self) -> str:
        url = self.config.get("list_url")
        if not isinstance(url, str) or not url.strip():
            raise ValueError("site_config.list_url is required for default fetch_list")
        return self.request_text(url)

    @abstractmethod
    def parse_list(self, response: str) -> list[Item]:
        """Return list entries; [] means a successfully parsed empty list."""
        raise NotImplementedError

    @abstractmethod
    def fetch_detail(self, item: Item) -> str:
        raise NotImplementedError

    @abstractmethod
    def parse_detail(self, response: str, item: Item) -> Parsed:
        raise NotImplementedError

    @abstractmethod
    def normalize(self, parsed: Parsed) -> Notice:
        raise NotImplementedError

    def _stage(self, stage: str, action: Callable[..., Result], *args: Any) -> Result:
        try:
            return action(*args)
        except Exception as error:
            self.logger.error(
                "scraper_failed source_id=%s stage=%s error_type=%s",
                self.source_id, stage, type(error).__name__,
            )
            raise ScraperError(self.source_id, stage, error) from error

    def _parse_items(self, response: str) -> list[Item]:
        items = self.parse_list(response)
        if not isinstance(items, list):
            raise TypeError("parse_list must return a list")
        return items

    def _normalize_notice(self, parsed: Parsed) -> Notice:
        notice = self.normalize(parsed)
        validate_notices([notice], self.source_id)
        return notice

    def run(self) -> list[Notice]:
        if not self.enabled:
            self.logger.info("scraper_skipped source_id=%s", self.source_id)
            return []
        response = self._stage("fetch_list", self.fetch_list)
        items = self._stage("parse_list", self._parse_items, response)
        notices: list[Notice] = []
        for item in items:
            detail = self._stage("fetch_detail", self.fetch_detail, item)
            parsed = self._stage("parse_detail", self.parse_detail, detail, item)
            notices.append(self._stage("normalize", self._normalize_notice, parsed))
        self.logger.info(
            "scraper_success source_id=%s notices=%d", self.source_id, len(notices),
        )
        return notices
