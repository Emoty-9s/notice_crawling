"""M03 fixtures and stability boundaries, without network dependencies."""

import json
import os
import subprocess
import sys
import unicodedata
import unittest
from pathlib import Path

from src.core.models import ContentHashGenerator, Notice, NoticeIdGenerator
from src.core.normalizer import (
    clean_content_text, generate_content_hash, generate_notice_id,
    html_to_content_text, normalize_date, normalize_institution,
    normalize_url, normalize_whitespace,
)


class TextAndDateTests(unittest.TestCase):
    def test_date_variations(self):
        fixtures = [
            "2026.10.30", "2026-10-30", "2026년 10월 30일",
            "2026.10.30(금)", " 2026. 10. 30. (금요일) ", "2026/10/30",
        ]
        for value in fixtures:
            with self.subTest(value=value):
                self.assertEqual(normalize_date(value), "2026-10-30")

    def test_leap_year_and_calendar_validation(self):
        self.assertEqual(normalize_date("2024.2.29"), "2024-02-29")
        for value in ("2026.2.29", "2026.13.1", "2026.4.31", "0000-01-01"):
            with self.subTest(value=value):
                self.assertIsNone(normalize_date(value))

    def test_dates_do_not_infer_missing_or_ambiguous_values(self):
        for value in (None, "", "상시", "10.30", "26.10.30", "2026-10",
                      "마감 2026-10-30", "2026-10-30 ~ 2026-11-01",
                      "2026-10-30T23:30:00-05:00", "2026-10.30"):
            with self.subTest(value=value):
                self.assertIsNone(normalize_date(value))
        with self.assertRaises(TypeError):
            normalize_date(20261030)

    def test_whitespace_unicode_and_institution(self):
        self.assertEqual(normalize_whitespace(" \t사업\r\n 공고\u00a0  모집\u3000"), "사업 공고 모집")
        self.assertEqual(normalize_institution("  (재)\n예시   기관  "), "(재) 예시 기관")
        self.assertEqual(normalize_institution("㈜예시"), "㈜예시")
        self.assertEqual(normalize_whitespace(unicodedata.normalize("NFD", "특허")), "특허")

    def test_plain_text_preserves_symbols_and_is_idempotent(self):
        self.assertEqual(clean_content_text("  조건: 1 < 2 & 예산 100원.\n"), "조건: 1 < 2 & 예산 100원.")
        text = clean_content_text("첫째\r\n\r\n 둘째\t 끝")
        self.assertEqual(clean_content_text(text), text)
        self.assertEqual(clean_content_text("\n\t "), "")

    def test_html_cleanup_preserves_content_and_removes_chrome(self):
        html = (
            '<head><title>문서 제목</title></head><header>로고</header>'
            '<nav>메뉴<script>ignore()</script></nav>'
            '<style>.x{color:red}</style><script>track()</script>'
            '<main><h1>공고</h1><p>예산 <b>100</b>원 &amp; 조건</p>'
            '<p>다음<br>줄</p><table><tr><td>A</td><td>B</td></tr></table></main>'
            '<footer>저작권</footer>'
        )
        self.assertEqual(html_to_content_text(html), "공고 예산 100원 & 조건 다음 줄 A B")
        self.assertEqual(html_to_content_text('<header/>본문<!-- 주석 -->'), "본문")
        self.assertEqual(html_to_content_text('<nav><header>메뉴</nav><p>본문</p>'), "본문")

    def test_text_type_errors_are_not_coerced(self):
        for function in (normalize_whitespace, normalize_institution,
                         clean_content_text, html_to_content_text):
            with self.subTest(function=function), self.assertRaises(TypeError):
                function(None)


class UrlTests(unittest.TestCase):
    def test_fragment_whitespace_host_and_default_port(self):
        self.assertEqual(
            normalize_url("  HTTPS://Example.ORG:443/Notice?id=7#section \n"),
            "https://example.org/Notice?id=7",
        )
        self.assertEqual(normalize_url("http://EXAMPLE.org:80"), "http://example.org/")
        self.assertEqual(normalize_url("https://[::1]:443/a#x"), "https://[::1]/a")

    def test_query_semantics_path_case_and_slashes_preserved(self):
        for value in (
            "https://example.org/Path/?id=2&id=1&empty=&q=a%20b",
            "https://example.org/Path?id=1", "https://example.org:8443/Path",
        ):
            with self.subTest(value=value):
                self.assertEqual(normalize_url(value), value)
                self.assertEqual(normalize_url(normalize_url(value)), value)
        self.assertNotEqual(normalize_url('https://example.org/A'), normalize_url('https://example.org/a'))

    def test_empty_and_invalid_urls(self):
        self.assertEqual(normalize_url(" \t"), "")
        for value in ("/detail/1", "javascript:open()", "https://", "https://a:99999/",
                      "https://example.org/a b", "https://exa\nmple.org", "https://user:pw@example.org/"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_url(value)
        with self.assertRaises(TypeError):
            normalize_url(None)


class StableIdentityTests(unittest.TestCase):
    def identity(self, **changes):
        values = dict(source_id="source-a", title="공고 제목", url="https://example.org/view?id=1")
        values.update(changes)
        return generate_notice_id(**values)

    def test_priority_site_id_over_number_title_and_url(self):
        first = self.identity(source_notice_id=" ID-1 ", notice_number="A")
        second = self.identity(source_notice_id="ID-1", notice_number="B", title="수정 제목", url="")
        self.assertEqual(first, second)
        self.assertNotEqual(first, self.identity(source_notice_id="ID-2"))

    def test_priority_number_over_url_and_title(self):
        first = self.identity(source_notice_id=" ", notice_number="제2026-1호")
        self.assertEqual(first, self.identity(notice_number="제2026-1호", title="변경", url=""))
        self.assertNotEqual(first, self.identity(notice_number="제2026-2호"))

    def test_stable_url_ignores_title_changes_and_fragment(self):
        first = self.identity(url=" HTTPS://EXAMPLE.org:443/view?id=1#top ")
        self.assertEqual(first, self.identity(title="수정된 제목"))
        self.assertNotEqual(first, self.identity(url="https://example.org/view?id=2"))

    def test_fallback_uses_normalized_title_and_canonical_url(self):
        first = self.identity(url="", title="  공고\n 제목  ")
        self.assertEqual(first, self.identity(url=" ", title="공고 제목"))
        self.assertNotEqual(first, self.identity(url="", title="다른 제목"))
        unstable = self.identity(url_is_stable=False, url="https://EXAMPLE.org:443/list#x")
        self.assertEqual(unstable, self.identity(url_is_stable=False, url="https://example.org/list"))
        self.assertNotEqual(unstable, self.identity(url_is_stable=False, url="https://example.org/list", title="다른 제목"))

    def test_source_and_identifier_kind_are_namespaced(self):
        first = self.identity(source_notice_id="1")
        self.assertNotEqual(first, self.identity(source_id="source-b", source_notice_id="1"))
        self.assertNotEqual(first, self.identity(notice_number="1"))
        self.assertNotEqual(self.identity(url="", title="c", source_id="ab"),
                            self.identity(url="", title="bc", source_id="a"))

    def test_zero_identifier_is_not_missing(self):
        self.assertEqual(self.identity(source_notice_id="0"), self.identity(source_notice_id="0", title="別", url=""))
        self.assertNotEqual(self.identity(source_notice_id="0"), self.identity())

    def test_identity_rejects_insufficient_or_wrong_typed_input(self):
        for values in ({"source_id": " "}, {"url": "", "title": " "},
                       {"url_is_stable": "yes"}, {"source_notice_id": 123}):
            with self.subTest(values=values), self.assertRaises((TypeError, ValueError)):
                self.identity(**values)

    def test_fresh_process_stability_across_hash_seeds(self):
        code = (
            "import json; from src.core.normalizer import generate_notice_id, generate_content_hash; "
            "print(json.dumps([generate_notice_id(source_id='site',title='title',url='https://example.org/1'),"
            "generate_content_hash(content_text='body text')]))"
        )
        results = []
        for seed in ("1", "777"):
            run = subprocess.run(
                [sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1],
                env={**os.environ, "PYTHONHASHSEED": seed}, capture_output=True,
                text=True, timeout=10, check=True,
            )
            results.append(json.loads(run.stdout))
        self.assertEqual(results[0], results[1])


class ContentHashTests(unittest.TestCase):
    def test_whitespace_and_unicode_equivalent_content(self):
        first = generate_content_hash(content_text="특허  공고\n 예산 100원")
        self.assertEqual(first, generate_content_hash(content_text=" 특허\t공고\u00a0예산 100원 "))
        self.assertEqual(first, generate_content_hash(content_text=unicodedata.normalize("NFD", "특허 공고 예산 100원")))

    def test_material_changes_are_significant(self):
        first = generate_content_hash(content_text="예산 100원. 마감 2026-11-01")
        for value in ("예산 101원. 마감 2026-11-01", "예산 100원. 마감 2026-11-02", "예산 100원! 마감 2026-11-01"):
            with self.subTest(value=value):
                self.assertNotEqual(first, generate_content_hash(content_text=value))

    def test_hash_algorithm_and_empty_body(self):
        self.assertEqual(generate_content_hash(content_text="abc"),
                         "content:v1:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        self.assertEqual(generate_content_hash(content_text=""), generate_content_hash(content_text=" \n"))
        with self.assertRaises(TypeError):
            generate_content_hash(content_text=None)

    def test_model_protocols_and_notice_integration(self):
        identity: NoticeIdGenerator = generate_notice_id
        content_hash: ContentHashGenerator = generate_content_hash
        url = normalize_url("https://EXAMPLE.org/1#x")
        text = html_to_content_text("<nav>홈</nav><p>협력기관&nbsp;모집</p>")
        notice = Notice(
            notice_id=identity(source_id="example", title="모집", url=url),
            source_id="example", institution=normalize_institution(" 예시 기관 "),
            title="모집", url=url, content_text=text,
            content_hash=content_hash(content_text=text), published_at=normalize_date("2026.10.30(금)"),
            first_seen_at="2026-10-30T00:00:00Z", last_seen_at="2026-10-30T00:00:00Z",
            updated_at="2026-10-30T00:00:00Z",
        )
        self.assertEqual(Notice.from_json(notice.to_json()), notice)
        self.assertEqual(notice.content_text, "협력기관 모집")
        self.assertEqual(notice.published_at, "2026-10-30")


if __name__ == "__main__":
    unittest.main()
