"""Pure M07 state/change/duplicate semantics with fixed observation times."""

import unittest
from dataclasses import replace

from src.core.diff import DiffConflictError, DiffInputError, TRACKED_FIELDS, compare_batch, compare_notice
from src.core.models import GeminiResult, GeminiStatus, Notice, NoticeStatus
from src.core.normalizer import generate_content_hash


FIRST = '2026-10-01T00:00:00Z'
LAST = '2026-10-29T00:00:00Z'
NOW = '2026-10-30T09:00:00+09:00'


def notice(notice_id='notice-1', **overrides):
    body = '공개 본문'
    values = dict(
        notice_id=notice_id, source_id='source', institution='예시 기관', title='공고 제목',
        url=f'https://example.test/view?id={notice_id}', content_text=body,
        content_hash=generate_content_hash(content_text=body), first_seen_at=FIRST,
        last_seen_at=LAST, updated_at=FIRST,
    )
    values.update(overrides)
    return Notice(**values)


class DiffTests(unittest.TestCase):
    def test_new_sets_observation_times_and_resets_incoming_status(self):
        current = notice(status='EXISTING')
        result = compare_notice(current, observed_at=NOW)
        self.assertIs(result.notice.status, NoticeStatus.NEW)
        self.assertEqual((result.notice.first_seen_at, result.notice.last_seen_at, result.notice.updated_at), (NOW, NOW, NOW))
        self.assertEqual(result.changes, ())
        self.assertEqual(current.first_seen_at, FIRST)
        self.assertIs(current.status, NoticeStatus.EXISTING)

    def test_unchanged_is_existing_and_keeps_first_and_updated(self):
        old = notice(status='UPDATED')
        result = compare_notice(notice(first_seen_at=NOW, updated_at=NOW), old, observed_at=NOW)
        self.assertIs(result.notice.status, NoticeStatus.EXISTING)
        self.assertEqual(result.notice.first_seen_at, FIRST)
        self.assertEqual(result.notice.last_seen_at, NOW)
        self.assertEqual(result.notice.updated_at, FIRST)
        self.assertFalse(result.content_changed)
        self.assertEqual(result.changed_fields, ())

    def test_body_and_hash_change_is_updated_and_reported(self):
        old = notice()
        body = '변경된 본문: 지원금 100원'
        current = replace(old, content_text=body, content_hash=generate_content_hash(content_text=body))
        result = compare_notice(current, old, observed_at=NOW)
        self.assertIs(result.notice.status, NoticeStatus.UPDATED)
        self.assertEqual(result.changed_fields, ('content_hash', 'content_text'))
        self.assertTrue(result.content_changed)
        self.assertEqual(result.changes[1].before, old.content_text)
        self.assertEqual(result.changes[1].after, body)
        self.assertEqual((result.notice.first_seen_at, result.notice.last_seen_at, result.notice.updated_at), (FIRST, NOW, NOW))

    def test_hash_alone_and_body_with_stale_hash_are_both_tracked(self):
        old = notice()
        for changes, expected in (({'content_hash': 'changed'}, ('content_hash',)),
                                  ({'content_text': '다른 내용'}, ('content_text',))):
            with self.subTest(changes=changes):
                result = compare_notice(replace(old, **changes), old, observed_at=NOW)
                self.assertIs(result.notice.status, NoticeStatus.UPDATED)
                self.assertEqual(result.changed_fields, expected)

    def test_each_important_field_causes_updated(self):
        old = notice()
        for field, value in {
            'title': '다른 제목', 'institution': '다른 기관', 'category': '입찰',
            'published_at': '2026-10-02', 'apply_start': '2026-10-03',
            'apply_end': '2026-11-03', 'url': 'https://example.test/new?id=1',
        }.items():
            with self.subTest(field=field):
                result = compare_notice(replace(old, **{field: value}), old, observed_at=NOW)
                self.assertIs(result.notice.status, NoticeStatus.UPDATED)
                self.assertEqual(result.changed_fields, (field,))
                self.assertFalse(result.content_changed)

    def test_optional_value_removed_is_tracked(self):
        old = notice(apply_end='2026-11-01')
        result = compare_notice(replace(old, apply_end=None), old, observed_at=NOW)
        self.assertEqual(result.changed_fields, ('apply_end',))
        self.assertIsNone(result.changes[0].after)

    def test_normalization_only_changes_are_existing_without_representation_churn(self):
        old = notice(published_at='2026-10-01')
        current = replace(old, title=' 공고\n제목 ', institution=' 예시\t기관 ',
                          content_text=' 공개\n본문 ', published_at='2026년 10월 1일',
                          url='HTTPS://EXAMPLE.TEST:443/view?id=notice-1#top')
        result = compare_notice(current, old, observed_at=NOW)
        self.assertIs(result.notice.status, NoticeStatus.EXISTING)
        self.assertEqual(result.notice.title, old.title)
        self.assertEqual(result.notice.content_text, old.content_text)
        self.assertEqual(result.notice.url, old.url)

    def test_unknown_dates_do_not_collapse_to_none(self):
        old = notice(apply_end='별도 안내')
        result = compare_notice(replace(old, apply_end='상시 접수'), old, observed_at=NOW)
        self.assertEqual(result.changed_fields, ('apply_end',))

    def test_existing_gemini_preserved_for_all_states_of_analysis(self):
        for status in GeminiStatus:
            gemini = GeminiResult(status=status, relevant=True, score=90, reason='이전 분석',
                                  analyzed_content_hash='old-body', analyzed_at=FIRST)
            old = notice(gemini=gemini)
            for changes in ({}, {'title': '제목 수정'}, {'content_hash': 'new-body'}):
                with self.subTest(status=status, changes=changes):
                    result = compare_notice(notice(**changes), old, observed_at=NOW)
                    self.assertIs(result.notice.gemini, gemini)
                    self.assertEqual(result.notice.gemini.analyzed_content_hash, 'old-body')

    def test_new_caller_supplied_gemini_is_not_reset(self):
        gemini = GeminiResult(status='SUCCESS', relevant=False, score=0)
        result = compare_notice(notice(gemini=gemini), observed_at=NOW)
        self.assertIs(result.notice.gemini, gemini)

    def test_status_gemini_and_timestamps_do_not_trigger_updated(self):
        old = notice(gemini=GeminiResult(status='SUCCESS', relevant=True))
        current = notice(status='NEW', first_seen_at=NOW, last_seen_at=NOW, updated_at=NOW)
        self.assertIs(compare_notice(current, old, observed_at=NOW).notice.status, NoticeStatus.EXISTING)

    def test_mixed_batch_keeps_first_occurrence_order(self):
        old = [notice('existing'), notice('updated')]
        current = [notice('new'), notice('updated', title='수정됨'), notice('existing')]
        result = compare_batch(current, old, observed_at=NOW)
        self.assertEqual([n.notice_id for n in result.notices], ['new', 'updated', 'existing'])
        self.assertEqual([n.status for n in result.notices], [NoticeStatus.NEW, NoticeStatus.UPDATED, NoticeStatus.EXISTING])
        self.assertEqual(result.results[1].changed_fields, ('title',))

    def test_equivalent_duplicates_are_compared_once_against_stored(self):
        old = notice(gemini=GeminiResult(status='SUCCESS', reason='보존'))
        current = notice(title='변경 제목')
        duplicate = replace(current, title=' 변경\n제목 ', last_seen_at=NOW, status='EXISTING')
        result = compare_batch([current, duplicate, current], [old], observed_at=NOW)
        self.assertEqual(len(result.notices), 1)
        self.assertIs(result.notices[0].status, NoticeStatus.UPDATED)
        self.assertEqual(result.duplicates[0].notice_id, current.notice_id)
        self.assertEqual(result.duplicates[0].input_indexes, (0, 1, 2))
        self.assertIs(result.notices[0].gemini, old.gemini)

    def test_new_duplicate_stays_new(self):
        current = notice()
        result = compare_batch([current, current], [], observed_at=NOW)
        self.assertEqual(len(result.notices), 1)
        self.assertIs(result.notices[0].status, NoticeStatus.NEW)

    def test_conflicting_duplicate_rejected_regardless_of_order(self):
        first = notice()
        for second in (replace(first, title='충돌'), replace(first, source_id='other'),
                       replace(first, gemini=GeminiResult(status='PENDING'))):
            for current in ([first, second], [second, first]):
                with self.subTest(second=second), self.assertRaises(DiffConflictError):
                    compare_batch(current, [], observed_at=NOW)

    def test_stored_duplicates_are_not_silently_overwritten(self):
        old = notice()
        with self.assertRaises(DiffConflictError):
            compare_batch([notice()], [old, old], observed_at=NOW)

    def test_different_identity_or_source_rejected(self):
        for previous in (notice('other'), notice(source_id='other')):
            with self.subTest(previous=previous), self.assertRaises(DiffInputError):
                compare_notice(notice(), previous, observed_at=NOW)
        with self.assertRaises(DiffInputError):
            compare_batch([notice(source_id='other')], [notice()], observed_at=NOW)

    def test_empty_batch_and_unseen_stored_records_not_modified(self):
        old = notice()
        self.assertEqual(compare_batch([], [old], observed_at=NOW).notices, [])
        self.assertEqual(old.last_seen_at, LAST)
        self.assertEqual(compare_batch([], [], observed_at=NOW).results, ())

    def test_input_instances_unchanged_and_repeated_output_deterministic(self):
        old, current = notice(), notice(title='변경')
        before = [old.to_json(), current.to_json()]
        first = compare_batch([current], [old], observed_at=NOW)
        second = compare_batch([current], [old], observed_at=NOW)
        self.assertEqual(first, second)
        self.assertEqual([old.to_json(), current.to_json()], before)

    def test_changed_fields_follow_fixed_contract_order(self):
        old = notice()
        current = replace(old, url='https://example.test/changed', title='다름', category='공고', content_hash='x')
        result = compare_notice(current, old, observed_at=NOW)
        self.assertEqual(result.changed_fields, tuple(f for f in TRACKED_FIELDS if f in ('url', 'title', 'category', 'content_hash')))

    def test_invalid_inputs_and_timestamps(self):
        for value in ('2026-10-30', '2026-10-30T09:00:00', 'invalid', None):
            with self.subTest(value=value), self.assertRaises(DiffInputError):
                compare_notice(notice(), observed_at=value)
        for current in (None, {}, replace(notice(), notice_id=' '), replace(notice(), url='relative')):
            with self.subTest(current=current), self.assertRaises(DiffInputError):
                compare_notice(current, observed_at=NOW)
        with self.assertRaises(DiffInputError):
            compare_batch([{}], [], observed_at=NOW)


if __name__ == '__main__':
    unittest.main()
