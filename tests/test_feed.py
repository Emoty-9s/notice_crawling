"""M09 offline projection, public contract, deterministic files and atomic I/O."""

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from src.core.models import GeminiResult, GeminiStatus, Notice
from src.core.storage import StorageIOError
from src.renderer.feed import FeedInputError, SUMMARY_LIMIT, build_feed, write_feed


STAMP = '2026-10-30T07:19:33Z'
PUBLIC_FIELDS = {
    'notice_id', 'source_id', 'institution', 'title', 'category', 'participation_type',
    'published_at', 'apply_start', 'apply_end', 'url', 'summary', 'keywords',
    'relevance_reason', 'first_seen_at', 'updated_at',
}


def notice(identifier='one', **overrides):
    fields = dict(
        notice_id=identifier, source_id='example', institution='예시 기관',
        title='IP-R&D 협력기관 모집', category='원본 게시판 분류',
        url='https://example.test/notice/' + identifier,
        content_text='특허법인  대상\n협력기관 모집', content_hash='body-hash',
        first_seen_at=STAMP, last_seen_at=STAMP, updated_at=STAMP,
        gemini=GeminiResult(
            status='SUCCESS', relevant=True, category='IP-R&D', participation_type='협력기관',
            keywords=['특허분석', '반도체'], reason='특허법인이 협력기관으로 참여 가능',
            analyzed_at=STAMP, analyzed_content_hash='body-hash',
        ),
    )
    fields.update(overrides)
    return Notice(**fields)


class FeedTests(unittest.TestCase):
    def test_relevant_only_and_all_non_success_states_excluded(self):
        good = notice()
        excluded = [replace(good, notice_id='irrelevant', gemini=replace(good.gemini, relevant=False))]
        excluded += [replace(good, notice_id=status.value, gemini=replace(good.gemini, status=status))
                     for status in GeminiStatus if status != GeminiStatus.SUCCESS]
        excluded.append(replace(good, notice_id='unknown', gemini=replace(good.gemini, relevant=None)))
        feed = build_feed([*excluded, good], generated_at=STAMP)
        self.assertEqual([record['notice_id'] for record in feed['notices']], ['one'])

    def test_empty_result_schema(self):
        expected = {'schema_version': 1, 'generated_at': STAMP, 'notices': []}
        self.assertEqual(build_feed([], generated_at=STAMP), expected)
        excluded = replace(notice(), gemini=GeminiResult(status='FAILED', relevant=True))
        self.assertEqual(build_feed([excluded], generated_at=STAMP), expected)

    def test_required_fields_and_structured_result_mapping(self):
        record = build_feed([notice()], generated_at=STAMP)['notices'][0]
        self.assertEqual(set(record), PUBLIC_FIELDS)
        self.assertEqual(record['category'], 'IP-R&D')
        self.assertEqual(record['participation_type'], '협력기관')
        self.assertEqual(record['keywords'], ['특허분석', '반도체'])
        self.assertEqual(record['relevance_reason'], '특허법인이 협력기관으로 참여 가능')
        self.assertIsNone(record['published_at'])
        self.assertIsNone(record['apply_start'])
        self.assertIsNone(record['apply_end'])
        self.assertEqual(record['first_seen_at'], STAMP)
        self.assertEqual(record['updated_at'], STAMP)

    def test_dates_are_preserved_and_empty_keywords_allowed(self):
        original = notice(published_at='2026-10-29', apply_start='2026-10-30', apply_end='2026-11-10')
        original = replace(original, gemini=replace(original.gemini, keywords=[]))
        record = build_feed([original], generated_at=STAMP)['notices'][0]
        for field in ('published_at', 'apply_start', 'apply_end'):
            self.assertEqual(record[field], getattr(original, field))
        self.assertEqual(record['keywords'], [])

    def test_summary_normalization_limit_and_no_full_content_distribution(self):
        original = notice(content_text='요약 대상 ' * 100 + 'BODY_TAIL_MUST_NOT_BE_PUBLIC')
        feed = build_feed([original], generated_at=STAMP)
        summary = feed['notices'][0]['summary']
        self.assertLessEqual(len(summary), SUMMARY_LIMIT)
        self.assertTrue(summary.endswith('…'))
        public_text = json.dumps(feed, ensure_ascii=False)
        for forbidden in ('content_text', 'content_hash', 'analyzed_content_hash', 'gemini', 'score', 'last_seen_at',
                          'BODY_TAIL_MUST_NOT_BE_PUBLIC'):
            self.assertNotIn(forbidden, public_text)
        self.assertNotIn(original.content_text, public_text)
        short = build_feed([notice()], generated_at=STAMP)['notices'][0]
        self.assertEqual(short['summary'], '특허법인 대상 협력기관 모집')

    def test_empty_body_summary_is_empty_string(self):
        self.assertEqual(build_feed([notice(content_text='')], generated_at=STAMP)['notices'][0]['summary'], '')

    def test_deterministic_order_and_same_notice_data_across_timestamps(self):
        values = [notice('z', source_id='b'), notice('z', source_id='a'), notice('a', source_id='a')]
        # IDs are globally unique, including across sources.
        values[0] = replace(values[0], notice_id='b-z')
        forward = build_feed(values, generated_at=STAMP)
        backward = build_feed(reversed(values), generated_at=STAMP)
        self.assertEqual(forward, backward)
        self.assertEqual([r['notice_id'] for r in forward['notices']], ['a', 'z', 'b-z'])
        later = build_feed(values, generated_at='2026-10-31T00:00:00Z')
        self.assertEqual(forward['notices'], later['notices'])
        self.assertNotEqual(forward['generated_at'], later['generated_at'])

    def test_generated_at_is_injected_and_canonical_utc(self):
        self.assertEqual(build_feed([], generated_at='2026-10-30T16:19:33+09:00')['generated_at'], STAMP)
        for invalid in (None, 12, '', 'today', '2026-10-30', '2026-10-30T07:19:33'):
            with self.subTest(value=invalid), self.assertRaises(FeedInputError):
                build_feed([], generated_at=invalid)

    def test_stale_or_incomplete_success_excluded(self):
        good = notice()
        for missing in ('category', 'participation_type', 'reason', 'keywords', 'analyzed_content_hash'):
            with self.subTest(missing=missing):
                old = replace(good, gemini=replace(good.gemini, **{missing: None}))
                self.assertEqual(build_feed([old], generated_at=STAMP)['notices'], [])
        stale = replace(good, content_hash='changed-body')
        self.assertEqual(build_feed([stale], generated_at=STAMP)['notices'], [])

    def test_notice_lifecycle_status_does_not_hide_relevant_existing(self):
        for status in ('NEW', 'UPDATED', 'EXISTING'):
            with self.subTest(status=status):
                self.assertEqual(len(build_feed([notice(status=status)], generated_at=STAMP)['notices']), 1)

    def test_duplicate_records_collapse_and_conflicts_are_explicit(self):
        original = notice()
        self.assertEqual(len(build_feed([original, original], generated_at=STAMP)['notices']), 1)
        conflicting = replace(original, title='변경된 제목')
        for values in ([original, conflicting], [conflicting, original]):
            with self.assertRaises(FeedInputError):
                build_feed(values, generated_at=STAMP)

    def test_inputs_not_modified_and_output_does_not_alias_keywords(self):
        original = notice()
        before = original.to_json()
        build_feed([original], generated_at=STAMP)['notices'][0]['keywords'].append('외부 변경')
        self.assertEqual(original.to_json(), before)

    def test_invalid_input_contract_is_explicit(self):
        with self.assertRaises(FeedInputError):
            build_feed([{}], generated_at=STAMP)
        with self.assertRaises(FeedInputError):
            build_feed([notice(notice_id=' ')], generated_at=STAMP)


class FeedFileTests(unittest.TestCase):
    def setUp(self):
        tests_root = Path(__file__).resolve().parent
        temp = tempfile.TemporaryDirectory(dir=tests_root, prefix='feed-test-')
        self.root = Path(temp.name).resolve()
        if self.root.parent != tests_root or not self.root.name.startswith('feed-test-'):
            raise RuntimeError('unexpected cleanup target')
        self.addCleanup(temp.cleanup)

    def test_write_self_contained_json_and_matching_metadata(self):
        paths = write_feed(iter([notice()]), generated_at=STAMP, output_dir=self.root/'public')
        self.assertEqual([p.name for p in paths], ['notices.json', 'metadata.json'])
        feed, metadata = [json.loads(p.read_text(encoding='utf-8')) for p in paths]
        self.assertEqual(set(feed), {'schema_version', 'generated_at', 'notices'})
        self.assertEqual(metadata, {'schema_version': 1, 'generated_at': STAMP, 'notice_count': 1})
        self.assertEqual(set(feed['notices'][0]), PUBLIC_FIELDS)

    def test_empty_files_and_count_after_filtering_and_dedup(self):
        good = notice()
        bad = replace(good, notice_id='bad', gemini=replace(good.gemini, relevant=False))
        paths = write_feed([good, good, bad], generated_at=STAMP, output_dir=self.root)
        self.assertEqual(json.loads(paths[1].read_text(encoding='utf-8'))['notice_count'], 1)
        paths = write_feed([], generated_at=STAMP, output_dir=self.root)
        self.assertEqual(json.loads(paths[0].read_text(encoding='utf-8'))['notices'], [])
        self.assertEqual(json.loads(paths[1].read_text(encoding='utf-8'))['notice_count'], 0)

    def test_deterministic_bytes_utf8_sorted_keys_and_lf(self):
        first = write_feed([notice('b'), notice('a')], generated_at=STAMP, output_dir=self.root)
        before = [p.read_bytes() for p in first]
        write_feed([notice('a'), notice('b')], generated_at=STAMP, output_dir=self.root)
        self.assertEqual([p.read_bytes() for p in first], before)
        for data in before:
            self.assertNotIn(b'\r', data)
            self.assertTrue(data.endswith(b'\n'))
            text = data.decode('utf-8')
            expected = json.dumps(json.loads(text), ensure_ascii=False, sort_keys=True, indent=2) + '\n'
            self.assertEqual(text, expected)
        self.assertIn('특허법인', before[0].decode('utf-8'))

    def test_invalid_input_preserves_existing_files(self):
        paths = write_feed([notice()], generated_at=STAMP, output_dir=self.root)
        before = [p.read_bytes() for p in paths]
        with self.assertRaises(FeedInputError):
            write_feed([notice(), notice(title='충돌')], generated_at=STAMP, output_dir=self.root)
        self.assertEqual([p.read_bytes() for p in paths], before)

    def test_first_atomic_replace_failure_preserves_existing_files(self):
        paths = write_feed([notice()], generated_at=STAMP, output_dir=self.root)
        before = [p.read_bytes() for p in paths]
        with patch('src.core.storage.os.replace', side_effect=OSError('simulated')), self.assertRaises(StorageIOError):
            write_feed([], generated_at=STAMP, output_dir=self.root)
        self.assertEqual([p.read_bytes() for p in paths], before)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['metadata.json', 'notices.json'])


if __name__ == '__main__':
    unittest.main()
