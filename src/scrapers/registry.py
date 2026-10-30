"""Explicit, ordered scraper registration and source-level failure isolation."""

from __future__ import annotations

import logging

from src.core.models import Notice
from src.scrapers.base import BaseScraper, ScraperError, validate_notices


class ScraperRegistry:
    """Run explicitly registered instances; never discover/enable sites implicitly.

    run returns successful sources' list[Notice]. Per-run results/errors/skipped
    distinguish a real empty source from a failed or disabled one, in memory
    only. Persistent health/status reporting belongs to later milestones.
    """

    def __init__(self, *, logger: logging.Logger | None = None) -> None:
        self._scrapers: dict[str, BaseScraper] = {}
        self.results: dict[str, list[Notice]] = {}
        self.errors: dict[str, ScraperError] = {}
        self.skipped: list[str] = []
        self.logger = logger if logger is not None else logging.getLogger(__name__)

    def register(self, scraper: BaseScraper) -> None:
        if not isinstance(scraper, BaseScraper):
            raise TypeError("registry requires a BaseScraper instance")
        if scraper.source_id in self._scrapers:
            raise ValueError(f"duplicate source_id: {scraper.source_id}")
        self._scrapers[scraper.source_id] = scraper

    def run(self) -> list[Notice]:
        self.results = {}
        self.errors = {}
        self.skipped = []
        notices: list[Notice] = []
        for source_id, scraper in tuple(self._scrapers.items()):
            if not scraper.enabled:
                self.skipped.append(source_id)
                self.logger.info("registry_skipped source_id=%s", source_id)
                continue
            try:
                source_notices = scraper.run()
                validate_notices(source_notices, source_id)
            except Exception as error:
                if isinstance(error, ScraperError):
                    failure = error
                else:
                    failure = ScraperError(source_id, "run", error)
                    failure.__cause__ = error
                self.errors[source_id] = failure
                self.logger.error(
                    "registry_failed source_id=%s stage=%s error_type=%s",
                    source_id, failure.stage, failure.error_type,
                )
                continue
            self.results[source_id] = source_notices.copy()
            notices.extend(source_notices)
        self.logger.info(
            "registry_complete successful=%d failed=%d skipped=%d notices=%d",
            len(self.results), len(self.errors), len(self.skipped), len(notices),
        )
        return notices


def build_mvp_registry(site_configs, *, transport_factory=None, clock=None, logger=None):
    """Register only the five M05 adapters, preserving configured enabled flags.

    No file loading or network execution. A caller supplies decoded site config
    mappings; transport_factory(source_id) optionally injects fixture transports.
    """
    from src.scrapers.khidi_business import KhidiBusinessScraper
    from src.scrapers.kised_bid_public import KisedBidPublicScraper
    from src.scrapers.rda_bid import RdaBidScraper
    from src.scrapers.seoul_rnd_notice import SeoulRndNoticeScraper
    from src.scrapers.kipa_bid import KipaBidScraper

    adapters = (KhidiBusinessScraper, KisedBidPublicScraper, RdaBidScraper,
                SeoulRndNoticeScraper, KipaBidScraper)
    configs = {}
    for config in site_configs:
        source_id = config['source_id']
        if source_id in configs:
            raise ValueError(f'duplicate site config: {source_id}')
        configs[source_id] = config
    missing = [adapter.source for adapter in adapters if adapter.source not in configs]
    if missing:
        raise ValueError(f'missing MVP configs: {missing}')
    registry = ScraperRegistry(logger=logger)
    for adapter in adapters:
        kwargs = {'clock': clock, 'logger': logger}
        if transport_factory is not None:
            kwargs['transport'] = transport_factory(adapter.source)
        registry.register(adapter(configs[adapter.source], **kwargs))
    return registry
