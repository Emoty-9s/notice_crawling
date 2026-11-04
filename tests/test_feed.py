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
    'relevance_reason', 'first_seen_at', 'updated_at', 'is_new',
}


def notice(identifier='one', **overrides):
    fields = dict(
        notice_id=identifier, source_id='example', institution='예시 기관',
        title='IP-R&D 협력기관 모집', category='원본 게시판 분류',
        url='https://example.test/notice/' + identifier,
        content_text='특허법인  대상\n협력기관 모집', content_hash='body-hash',
        first_seen_at=STAMP, last_seen_at=STAMP, updated_at=STAMP,
        gemini=GeminiResult(
            status='SUCCESS', analysis_policy='patent-firm-participation-v2', relevant=True, category='IP-R&D', participation_type='협력기관',
            keywords=['특허분석', '반도체'], reason='특허법인이 협력기관으로 참여 가능',
            analyzed_at=STAMP, analyzed_content_hash='body-hash',
        ),
    )
    fields.update(overrides)
    return Notice(**fields)


class FeedTests(unittest.TestCase):
    def test_gemini_status_never_controls_v3_publication(self):
        good=notice()
        records=[replace(good,notice_id=s.value,gemini=replace(good.gemini,status=s)) for s in GeminiStatus]
        records.append(replace(good,notice_id='negative',gemini=replace(good.gemini,relevant=False)))
        feed=build_feed(records,generated_at=STAMP)
        self.assertEqual(len(feed['notices']),5)
        self.assertTrue(all('relevance_reason' not in n for n in feed['notices']))

    def test_empty_result_schema(self):
        self.assertEqual(build_feed([],generated_at=STAMP),dict(schema_version=3,generated_at=STAMP,notices=[]))
        unrelated=notice(title='청소 용역 계약',category=None,content_text='청소 용역 계약의 구체적인 수행 사항과 시설 청소 내용입니다.')
        self.assertEqual(build_feed([unrelated],generated_at=STAMP)['notices'],[])

    def test_required_fields_and_public_prefilter_mapping(self):
        from src.local_client.sync import V3_NOTICE_FIELDS
        record=build_feed([notice()],generated_at=STAMP)['notices'][0]
        self.assertEqual(set(record),V3_NOTICE_FIELDS)
        self.assertEqual(record['prefilter_status'],'CANDIDATE')
        self.assertNotIn('category',record)
        self.assertIn('특허법인',record['content_text'])
        self.assertIsNone(record['apply_end'])
        self.assertEqual(record['updated_at'],STAMP)

    def test_dates_are_preserved_without_model_keywords(self):
        original=notice(published_at='2026-10-29',apply_start='2026-10-30',apply_end='2026-11-10')
        record=build_feed([original],generated_at=STAMP)['notices'][0]
        for field in ('published_at','apply_start','apply_end'): self.assertEqual(record[field],getattr(original,field))
        self.assertNotIn('keywords',record)

    def test_summary_limit_full_evidence_and_contact_minimization(self):
        original=notice(content_text='특허분석 용역 '+('공개 설명 '*100)+' 참가 자격: 특허법인 담당자: 홍길동 02-123-4567 person@example.test')
        record=build_feed([original],generated_at=STAMP)['notices'][0]
        self.assertLessEqual(len(record['summary']),SUMMARY_LIMIT)
        self.assertTrue(record['summary'].endswith('…'))
        self.assertIn('참가 자격: 특허법인',record['content_text'])
        for private in ('홍길동','02-123-4567','person@example.test'): self.assertNotIn(private,record['content_text'])
        self.assertNotIn('gemini',record);self.assertNotIn('analysis',record)

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
        self.assertTrue(all(n['is_new'] for n in forward['notices']))
        self.assertFalse(any(n['is_new'] for n in later['notices']))
        self.assertEqual([{k:v for k,v in n.items() if k != 'is_new'} for n in forward['notices']],
                         [{k:v for k,v in n.items() if k != 'is_new'} for n in later['notices']])
        self.assertNotEqual(forward['generated_at'], later['generated_at'])

    def test_generated_at_is_injected_and_canonical_utc(self):
        self.assertEqual(build_feed([], generated_at='2026-10-30T16:19:33+09:00')['generated_at'], STAMP)
        for invalid in (None, 12, '', 'today', '2026-10-30', '2026-10-30T07:19:33'):
            with self.subTest(value=invalid), self.assertRaises(FeedInputError):
                build_feed([], generated_at=invalid)

    def test_stale_or_incomplete_legacy_analysis_is_preserved_not_required(self):
        good=notice()
        for missing in ('category','participation_type','reason','keywords','analyzed_content_hash'):
            old=replace(good,gemini=replace(good.gemini,**{missing:None}))
            self.assertEqual(len(build_feed([old],generated_at=STAMP)['notices']),1)
        self.assertEqual(len(build_feed([replace(good,content_hash='changed')],generated_at=STAMP)['notices']),1)

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

    def test_inputs_and_historical_analysis_are_not_modified(self):
        original=notice();before=original.to_json()
        record=build_feed([original],generated_at=STAMP)['notices'][0]
        record['content_text']='modified outside history'
        self.assertEqual(original.to_json(),before)

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
        self.assertEqual(metadata, {'schema_version': 3, 'generated_at': STAMP, 'notice_count': 1})
        from src.local_client.sync import V3_NOTICE_FIELDS
        self.assertEqual(set(feed['notices'][0]), V3_NOTICE_FIELDS)

    def test_empty_files_and_count_after_filtering_and_dedup(self):
        good = notice()
        bad = replace(good, notice_id='bad',title='청소 용역',category=None,content_text='청소 용역 계약의 시설 청소 작업에 관한 구체적 사항입니다.')
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
