"""Image-only bodies observed live on KHIDI and Seoul, 2026-11-02."""
import unittest
from dataclasses import replace

from _site_cases import fixture_context, body_container
from src.scrapers._html import StructureError, parse_html


class ImageOnlyNoticeTests(unittest.TestCase):
    def parse_body(self, source, html):
        scraper, _, detail, _, item = fixture_context(source)
        root = parse_html(detail)
        body = body_container(scraper, root)
        body.children = parse_html(html).children
        return scraper, scraper.parse_detail(root.html(), item)

    def test_external_poster_collected_without_inventing_text(self):
        for source in ('khidi_business', 'seoul_rnd_notice'):
            with self.subTest(source=source):
                scraper, parsed = self.parse_body(source, '<p><img src="/poster.png" alt="external_image"></p>')
                self.assertIn('OCR 미수행', parsed.content_text)
                self.assertIn('/poster.png', parsed.content_text)
                notice = scraper.normalize(parsed)
                changed = scraper.normalize(replace(parsed, content_text=parsed.content_text.replace('poster.png', 'changed.png')))
                self.assertEqual(notice.notice_id, changed.notice_id)
                self.assertNotEqual(notice.content_hash, changed.content_hash)

    def test_inline_image_identity_is_hashed_without_base64_payload(self):
        _, first = self.parse_body('seoul_rnd_notice', '<img src="data:image/png;base64,aW1hZ2Ux">')
        _, second = self.parse_body('seoul_rnd_notice', '<img src="data:image/png;base64,aW1hZ2Uy">')
        self.assertIn('embedded-image-sha256:', first.content_text)
        self.assertNotIn('aW1hZ2Ux', first.content_text)
        self.assertNotEqual(first.content_text, second.content_text)

    def test_empty_invalid_or_script_body_still_fails(self):
        for source in ('khidi_business', 'seoul_rnd_notice'):
            for html in ('', '<script>hidden</script>', '<img>', '<img src="javascript:alert(1)">', '<img src="data:image/png;base64,====">'):
                with self.subTest(source=source, html=html), self.assertRaises(StructureError):
                    self.parse_body(source, html)

    def test_text_body_remains_unchanged(self):
        for source in ('khidi_business', 'seoul_rnd_notice'):
            _, parsed = self.parse_body(source, '<p>실제 본문</p><img src="/poster.png">')
            self.assertEqual(parsed.content_text, '실제 본문')
