"""Offline fixture downloader checks; every HTTP request is a fake."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import URLError

from tools.fetch_fixtures import TARGETS, collect, fetch_fixture, main


def response(data=b"<!doctype html><html><body>notice</body></html>", content_type="text/html"):
    result = Mock()
    result.getcode.return_value = 200
    result.read.return_value = data
    result.headers = {"Content-Type": content_type}
    result.__enter__ = Mock(return_value=result)
    result.__exit__ = Mock(return_value=False)
    return result


class FetchFixtureTests(unittest.TestCase):
    def setUp(self):
        workspace_tests = Path(__file__).resolve().parent
        temporary = tempfile.TemporaryDirectory(dir=workspace_tests, prefix="fixture-fetch-test-")
        self.root = Path(temporary.name).resolve()
        # Verify the exact recursive-cleanup target stays inside this workspace.
        if self.root.parent != workspace_tests or not self.root.name.startswith("fixture-fetch-test-"):
            raise RuntimeError("unexpected temporary directory")
        self.addCleanup(temporary.cleanup)

    def fetch(self, destination, opener, **options):
        return fetch_fixture(
            "https://example.test/list", destination, opener=opener,
            timeout=7, user_agent="FixtureTest/1", **options,
        )

    def test_original_encoding_bytes_timeout_and_user_agent(self):
        data = '<html><body>실제 공고</body></html>'.encode('cp949')
        fake = response(data, "text/html; charset=EUC-KR")
        opener = Mock(return_value=fake)
        path = self.root / "source" / "list.html"
        self.assertEqual(self.fetch(path, opener), "SAVED")
        self.assertEqual(path.read_bytes(), data)
        self.assertEqual(opener.call_args.kwargs, {"timeout": 7})
        request = opener.call_args.args[0]
        self.assertEqual(request.get_header("User-agent"), "FixtureTest/1")
        fake.__exit__.assert_called_once()

    def test_existing_fixture_is_skipped_without_network(self):
        path = self.root / "list.html"
        path.write_bytes(b"existing")
        opener = Mock(side_effect=AssertionError("must not request"))
        self.assertEqual(self.fetch(path, opener), "SKIPPED")
        self.assertEqual(path.read_bytes(), b"existing")
        opener.assert_not_called()

    def test_explicit_overwrite_replaces_and_leaves_no_temporary_files(self):
        path = self.root / "list.html"
        path.write_bytes(b"old")
        data = b"<html><body>new</body></html>"
        self.assertEqual(self.fetch(path, Mock(return_value=response(data)), overwrite=True), "SAVED")
        self.assertEqual(path.read_bytes(), data)
        self.assertEqual(list(self.root.iterdir()), [path])

    def test_failed_download_preserves_existing_fixture(self):
        path = self.root / "detail.html"
        path.write_bytes(b"old")
        with self.assertRaises(URLError):
            self.fetch(path, Mock(side_effect=URLError("DNS failure")), overwrite=True)
        self.assertEqual(path.read_bytes(), b"old")

    def test_failure_does_not_stop_other_endpoint_or_sites(self):
        opener = Mock(side_effect=[URLError("failure")] + [response() for _ in range(9)])
        with contextlib.redirect_stdout(io.StringIO()):
            counts = collect(list(TARGETS), output=self.root, opener=opener)
        self.assertEqual(counts, {"SAVED": 9, "SKIPPED": 0, "FAILED": 1})
        self.assertEqual(len(list(self.root.rglob("*.html"))), 9)
        self.assertTrue((self.root / "khidi_business" / "detail.html").exists())
        self.assertFalse((self.root / "khidi_business" / "list.html").exists())

    def test_non_html_and_empty_responses_not_saved(self):
        for data, content_type in [(b"", "text/html"), (b"{}", "application/json"),
                                    (b"server error", "text/html")]:
            path = self.root / "list.html"
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.fetch(path, Mock(return_value=response(data, content_type)))
            self.assertFalse(path.exists())

    def test_cli_reports_failure_exit_and_selected_site(self):
        with patch("tools.fetch_fixtures.urlopen", side_effect=URLError("offline")) as opener:
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["--site", "kipa_bid", "--output-dir", str(self.root)])
        self.assertEqual(code, 1)
        self.assertEqual(opener.call_count, 2)
        self.assertEqual(list(self.root.rglob("*.html")), [])

    def test_all_existing_files_produce_success_without_network(self):
        for source in TARGETS:
            folder = self.root / source
            folder.mkdir()
            for kind in ("list", "detail"):
                (folder / f"{kind}.html").write_bytes(b"existing")
        with patch("tools.fetch_fixtures.urlopen", side_effect=AssertionError("network forbidden")) as opener:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--output-dir", str(self.root)]), 0)
        opener.assert_not_called()

    def test_invalid_timeout_fails_before_network(self):
        for value in ("0", "-1", "nan", "inf"):
            with self.subTest(value=value), patch("tools.fetch_fixtures.urlopen") as opener:
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as error:
                        main(["--timeout", value])
                self.assertEqual(error.exception.code, 2)
                opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
