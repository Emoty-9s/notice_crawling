"""Fake-only M04 lifecycle, HTTP options/retries and registry isolation."""

import json
import logging
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from src.core.models import Notice
from src.core.normalizer import (
    generate_content_hash, generate_notice_id, normalize_date,
    normalize_institution, normalize_url, normalize_whitespace,
)
from src.scrapers.base import BaseScraper, HttpSettings, ScraperError, UrllibTransport
from src.scrapers.registry import ScraperRegistry


class FakeScraper(BaseScraper[dict, dict]):
    """In-memory JSON fixture adapter, not a real site implementation."""

    def parse_list(self, response):
        return json.loads(response)

    def fetch_detail(self, item):
        return self.request_text(item["url"])

    def parse_detail(self, response, item):
        return {**json.loads(response), "url": item["url"], "id": item["id"]}

    def normalize(self, parsed):
        url = normalize_url(parsed["url"])
        title = normalize_whitespace(parsed["title"])
        body = normalize_whitespace(parsed["body"])
        return Notice(
            notice_id=generate_notice_id(
                source_id=self.source_id, title=title, url=url,
                source_notice_id=parsed["id"],
            ),
            source_id=self.source_id, institution=normalize_institution(self.config["institution"]),
            title=title, url=url, content_text=body,
            content_hash=generate_content_hash(content_text=body),
            published_at=normalize_date(parsed["published_at"]),
            first_seen_at="2026-10-30T00:00:00Z", last_seen_at="2026-10-30T00:00:00Z",
            updated_at="2026-10-30T00:00:00Z",
        )


def make_scraper(source_id="fake", *, enabled=True, responses=None, **kwargs):
    transport = Mock()
    if responses is None:
        responses = [
            json.dumps([{"id": "1", "url": "https://example.test/detail/1"}]),
            json.dumps({"title": " 모집  공고 ", "body": " 웹\n본문 ", "published_at": "2026.10.30(금)"}),
        ]
    transport.get.side_effect = responses
    kwargs.setdefault("sleep", Mock())
    kwargs.setdefault("logger", Mock(spec=logging.Logger))
    return FakeScraper(
        {"source_id": source_id, "institution": " 예시  기관 ",
         "list_url": "https://example.test/list", "enabled": enabled},
        transport=transport, **kwargs,
    )


class BaseScraperTests(unittest.TestCase):
    def test_mock_end_to_end_returns_normalized_notices(self):
        scraper = make_scraper()
        result = scraper.run()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        notice = result[0]
        self.assertIsInstance(notice, Notice)
        self.assertEqual(notice.source_id, "fake")
        self.assertEqual(notice.title, "모집 공고")
        self.assertEqual(notice.institution, "예시 기관")
        self.assertEqual(notice.content_text, "웹 본문")
        self.assertEqual(notice.published_at, "2026-10-30")
        self.assertEqual(Notice.from_json(notice.to_json()), notice)
        self.assertEqual(scraper.transport.get.call_count, 2)
        scraper.logger.info.assert_called_with("scraper_success source_id=%s notices=%d", "fake", 1)

    def test_empty_list_skips_detail(self):
        scraper = make_scraper(responses=["[]"])
        self.assertEqual(scraper.run(), [])
        self.assertEqual(scraper.transport.get.call_count, 1)

    def test_disabled_scraper_never_fetches(self):
        scraper = make_scraper(enabled=False)
        self.assertEqual(scraper.run(), [])
        scraper.transport.get.assert_not_called()

    def test_list_parsing_failure_has_source_stage_and_cause(self):
        scraper = make_scraper(responses=["{broken"])
        with self.assertRaises(ScraperError) as context:
            scraper.run()
        error = context.exception
        self.assertEqual((error.source_id, error.stage), ("fake", "parse_list"))
        self.assertIsInstance(error.__cause__, json.JSONDecodeError)
        self.assertEqual(scraper.transport.get.call_count, 1)
        scraper._sleep.assert_not_called()
        scraper.logger.error.assert_called_once()

    def test_all_stages_report_failures(self):
        for stage in ("fetch_list", "parse_list", "fetch_detail", "parse_detail", "normalize"):
            scraper = make_scraper()
            with self.subTest(stage=stage), patch.object(scraper, stage, side_effect=ValueError("bad data")):
                with self.assertRaises(ScraperError) as context:
                    scraper.run()
                self.assertEqual(context.exception.stage, stage)
                scraper._sleep.assert_not_called()

    def test_parse_list_must_return_list(self):
        for response in ("null", "{}", '"not a list"'):
            with self.subTest(response=response), self.assertRaises(ScraperError) as context:
                make_scraper(responses=[response]).run()
            self.assertEqual(context.exception.stage, "parse_list")

    def test_normalize_must_return_notice_from_same_source(self):
        other = make_scraper("other").run()[0]
        for value in ({"title": "wrong"}, None, other):
            scraper = make_scraper()
            with self.subTest(value=value), patch.object(scraper, "normalize", return_value=value):
                with self.assertRaises(ScraperError) as context:
                    scraper.run()
                self.assertEqual(context.exception.stage, "normalize")

    def test_config_snapshot_and_http_settings(self):
        config = {"source_id": "a", "enabled": True, "list_url": "https://example.test/list",
                  "http": {"timeout_seconds": 3, "max_retries": 0, "user_agent": "ExampleAgent/1.0"}}
        transport = Mock()
        transport.get.return_value = "[]"
        scraper = FakeScraper(config, transport=transport)
        config["http"]["timeout_seconds"] = 99
        config["list_url"] = "https://changed.test/"
        self.assertEqual(scraper.run(), [])
        transport.get.assert_called_once_with(
            "https://example.test/list", timeout=3, headers={"User-Agent": "ExampleAgent/1.0"})
        self.assertEqual(scraper.config["http"]["timeout_seconds"], 3)
        with self.assertRaises(TypeError):
            scraper.config["enabled"] = False

    def test_transient_retry_succeeds_with_backoff_and_options(self):
        scraper = make_scraper(
            responses=[TimeoutError(), URLError("temporary"), "[]"],
            http_settings=HttpSettings(timeout_seconds=2, max_retries=2, backoff_seconds=0.25, user_agent="TestAgent/1"),
        )
        self.assertEqual(scraper.run(), [])
        self.assertEqual(scraper.transport.get.call_count, 3)
        self.assertEqual([c.args[0] for c in scraper._sleep.call_args_list], [0.25, 0.5])
        for call in scraper.transport.get.call_args_list:
            self.assertEqual(call.kwargs, {"timeout": 2, "headers": {"User-Agent": "TestAgent/1"}})

    def test_retry_exhaustion_and_zero_retries(self):
        for retries in (0, 2):
            scraper = make_scraper(responses=[TimeoutError()] * (retries + 1),
                                   http_settings=HttpSettings(max_retries=retries))
            with self.subTest(retries=retries), self.assertRaises(ScraperError) as context:
                scraper.run()
            self.assertEqual(context.exception.stage, "fetch_list")
            self.assertEqual(scraper.transport.get.call_count, retries + 1)
            self.assertEqual(scraper._sleep.call_count, retries)

    def test_http_status_retry_policy_and_backoff_cap(self):
        for status in (429, 500, 502, 503, 504, 400, 401, 403, 404):
            error = HTTPError("https://example.test/", status, "failure", {}, None)
            scraper = make_scraper(responses=[error, "[]"],
                                   http_settings=HttpSettings(max_retries=1, backoff_seconds=50))
            with self.subTest(status=status):
                if status in (429, 500, 502, 503, 504):
                    self.assertEqual(scraper.run(), [])
                    scraper._sleep.assert_called_once_with(30.0)
                else:
                    with self.assertRaises(ScraperError):
                        scraper.run()
                    self.assertEqual(scraper.transport.get.call_count, 1)
                    scraper._sleep.assert_not_called()

    def test_non_text_transport_output_not_retried(self):
        scraper = make_scraper(responses=[b"[]"])
        with self.assertRaises(ScraperError) as context:
            scraper.run()
        self.assertEqual(context.exception.stage, "fetch_list")
        self.assertEqual(scraper.transport.get.call_count, 1)

    def test_invalid_config_and_http_settings(self):
        for values in ({"timeout_seconds": 0}, {"timeout_seconds": float("nan")},
                       {"backoff_seconds": -1}, {"max_retries": True},
                       {"max_retries": 11}, {"user_agent": ""}, {"user_agent": "Agent\r\nX: y"}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                HttpSettings(**values)
        for config in ({}, {"source_id": " "}, {"source_id": "a", "enabled": "false"}):
            with self.subTest(config=config), self.assertRaises(ValueError):
                FakeScraper(config)
        scraper = FakeScraper({"source_id": "a"}, transport=Mock())
        self.assertFalse(scraper.enabled)
        with self.assertRaises(ScraperError) as context:
            FakeScraper({"source_id": "a", "enabled": True}, transport=Mock(), logger=Mock()).run()
        self.assertEqual(context.exception.stage, "fetch_list")

    def test_urllib_adapter_uses_timeout_ua_and_closes_response_without_network(self):
        response = Mock()
        response.headers.get_content_charset.return_value = "utf-8"
        response.read.return_value = "공고".encode()
        with patch("src.scrapers.base.urlopen") as opener:
            opener.return_value.__enter__.return_value = response
            text = UrllibTransport().get("https://example.test/", timeout=4, headers={"User-Agent": "Fake/1"})
            self.assertEqual(text, "공고")
            self.assertEqual(opener.call_args.kwargs["timeout"], 4)
            self.assertEqual(opener.call_args.args[0].get_header("User-agent"), "Fake/1")
            opener.return_value.__exit__.assert_called_once()


class RegistryTests(unittest.TestCase):
    def registry(self, *scrapers):
        registry = ScraperRegistry(logger=Mock(spec=logging.Logger))
        for scraper in scrapers:
            registry.register(scraper)
        return registry

    def test_failed_source_does_not_block_following_source(self):
        registry = self.registry(make_scraper("bad", responses=["invalid"]), make_scraper("good"))
        result = registry.run()
        self.assertEqual([n.source_id for n in result], ["good"])
        self.assertTrue(all(isinstance(n, Notice) for n in result))
        self.assertEqual(set(registry.errors), {"bad"})
        self.assertEqual(registry.errors["bad"].stage, "parse_list")
        self.assertEqual(set(registry.results), {"good"})

    def test_empty_failed_and_disabled_are_distinguishable(self):
        disabled = make_scraper("disabled", enabled=False)
        registry = self.registry(make_scraper("empty", responses=["[]"]),
                                 make_scraper("bad", responses=["invalid"]), disabled)
        self.assertEqual(registry.run(), [])
        self.assertEqual(registry.results, {"empty": []})
        self.assertEqual(set(registry.errors), {"bad"})
        self.assertEqual(registry.skipped, ["disabled"])
        disabled.transport.get.assert_not_called()

    def test_partial_source_results_not_published_on_detail_failure(self):
        bad = make_scraper("bad", responses=[
            json.dumps([{"id": "1", "url": "https://example.test/1"}, {"id": "2", "url": "https://example.test/2"}]),
            json.dumps({"title": "ok", "body": "ok", "published_at": None}), "invalid",
        ])
        registry = self.registry(bad, make_scraper("good"))
        self.assertEqual([n.source_id for n in registry.run()], ["good"])
        self.assertNotIn("bad", registry.results)
        self.assertEqual(registry.errors["bad"].stage, "parse_detail")

    def test_registry_validates_overridden_run_and_handles_unexpected_error(self):
        for output in (None, {}, ["bad"], [make_scraper("other").run()[0]]):
            bad = make_scraper("bad")
            with self.subTest(output=output), patch.object(bad, "run", return_value=output):
                registry = self.registry(bad, make_scraper("good"))
                self.assertEqual([n.source_id for n in registry.run()], ["good"])
                self.assertEqual(registry.errors["bad"].stage, "run")
        bad = make_scraper("bad")
        with patch.object(bad, "run", side_effect=RuntimeError("bug")):
            registry = self.registry(bad, make_scraper("good"))
            self.assertEqual(len(registry.run()), 1)
            self.assertIsInstance(registry.errors["bad"].__cause__, RuntimeError)

    def test_registration_order_duplicate_guard_and_empty_registry(self):
        registry = self.registry(make_scraper("second"), make_scraper("first"))
        with self.assertRaises(ValueError):
            registry.register(make_scraper("first"))
        with self.assertRaises(TypeError):
            registry.register(object())
        self.assertEqual([n.source_id for n in registry.run()], ["second", "first"])
        self.assertEqual(self.registry().run(), [])

    def test_per_run_state_does_not_retain_previous_errors(self):
        scraper = make_scraper(responses=["invalid", "[]"])
        registry = self.registry(scraper)
        self.assertEqual(registry.run(), [])
        self.assertIn("fake", registry.errors)
        self.assertEqual(registry.run(), [])
        self.assertEqual(registry.errors, {})
        self.assertEqual(registry.results, {"fake": []})

    def test_keyboard_interrupt_is_not_swallowed(self):
        bad = make_scraper()
        with patch.object(bad, "run", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.registry(bad).run()


if __name__ == "__main__":
    unittest.main()
