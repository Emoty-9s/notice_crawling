"""M14 rule acceptance, deterministic ranking and local integration tests."""

import copy
import json
import tempfile
import unicodedata
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from src.core.models import GeminiResult, Notice
from src.local_client.matcher import MatchInputError, MatchWeights, match_notice, match_store
from src.local_client.performance import Performance, PerformanceDatabaseError, PerformanceStore
from src.local_client.sync import FeedClient
from _v2_fixture import build_feed


NOTICE = {
    'category': 'IP-R&D', 'participation_type': '협력기관',
    'keywords': ['반도체', 'IP-R&D', '특허분석'],
    'title': '반도체 IP-R&D 특허분석 협력기관 모집', 'summary': '특허분석 수행기관 모집',
}
RELATED = Performance(
    performance_id='P001', project_name='반도체 IP-R&D 특허분석', year=2025,
    technical_field='반도체', work_type='특허분석', keywords=['반도체', 'IP-R&D', '특허분석'],
    client='private-client-marker', attorneys=['private-attorney-marker'], notes='private-notes-marker',
)
UNRELATED = Performance(performance_id='P002', project_name='건축 설계', year=2000,
                        technical_field='건축', work_type='설계', keywords=['건축'])


def match(records, notice=NOTICE, **kwargs):
    return match_notice(notice, records, reference_year=2026, **kwargs)


class MatcherTests(unittest.TestCase):
    def setUp(self):
        blocked = patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('network forbidden'))
        blocked.start()
        self.addCleanup(blocked.stop)

    def test_default_score_and_explanation_sum_are_exact(self):
        result = match([RELATED])[0]
        self.assertEqual(result.score, 22)
        self.assertEqual({reason.rule: reason.points for reason in result.reasons}, {
            'technical_field': 5, 'work_type': 5, 'keyword': 6, 'category': 3, 'title': 2, 'recent': 1})
        self.assertEqual(result.score, sum(reason.points for reason in result.reasons))
        self.assertEqual(result.matched_terms, ('ip-r&d', '반도체', '특허분석'))

    def test_same_input_same_result_and_order_of_records_does_not_matter(self):
        expected = match([RELATED, UNRELATED])
        self.assertEqual(expected, match([RELATED, UNRELATED]))
        self.assertEqual(expected, match(iter([UNRELATED, RELATED])))
        self.assertEqual(expected[0].to_dict(), match([RELATED])[0].to_dict())

    def test_related_first_partial_second_unrelated_last(self):
        partial = Performance(performance_id='PARTIAL', project_name='다른 과제', technical_field='반도체', year=2000)
        results = match([UNRELATED, partial, RELATED])
        self.assertEqual([(r.performance_id, r.score) for r in results], [('P001', 22), ('PARTIAL', 7), ('P002', 0)])

    def test_keyword_duplicates_case_whitespace_and_repeated_body_do_not_inflate_score(self):
        notice = copy.deepcopy(NOTICE)
        notice['keywords'] += ['반도체', '  반도체  ', 'ip-r&d', 'IP-R&D', '특허분석']
        notice['summary'] += ' 반도체 특허분석 반도체 특허분석'
        record = replace(RELATED, keywords=list(RELATED.keywords)*5, description='반도체 반도체 특허분석 특허분석')
        self.assertEqual(match([record], notice=notice), match([RELATED]))

    def test_keyword_order_never_changes_points_or_explanation(self):
        notice = {**NOTICE, 'keywords': list(reversed(NOTICE['keywords']))}
        record = replace(RELATED, keywords=list(reversed(RELATED.keywords)))
        self.assertEqual(match([record], notice=notice), match([RELATED]))

    def test_korean_unicode_composition_and_fullwidth_case_are_normalized(self):
        notice = copy.deepcopy(NOTICE)
        for name in ('title', 'summary', 'category', 'participation_type'):
            notice[name] = unicodedata.normalize('NFD', notice[name])
        notice['keywords'] = [unicodedata.normalize('NFD', '반도체'), 'ＩＰ－Ｒ＆Ｄ', '특허분석']
        self.assertEqual(match([RELATED], notice=notice), match([RELATED]))

    def test_multiword_technical_field_matches_as_a_whole_phrase(self):
        notice = {**NOTICE, 'keywords': ['첨단 소재'], 'title': '첨단 소재 연구', 'summary': ''}
        record = Performance(performance_id='M', project_name='과제', technical_field='첨단 소재')
        result = match([record], notice=notice)[0]
        self.assertEqual(result.score, 7)
        self.assertEqual(result.matched_terms, ('첨단 소재',))

    def test_partial_korean_and_ascii_substrings_do_not_match(self):
        notice = {'category': '', 'participation_type': '', 'keywords': ['AI', '반도체'],
                  'title': 'chair 반도체장비', 'summary': ''}
        record = Performance(performance_id='B', project_name='chair 반도체장비')
        result = match([record], notice=notice, weights=MatchWeights(title=0))[0]
        self.assertEqual(result.score, 0)
        self.assertEqual(result.matched_terms, ())
        record = replace(record, technical_field='AI', work_type='반도체')
        self.assertEqual(match([record], notice={**notice, 'keywords': []}, weights=MatchWeights(title=0))[0].score, 0)

    def test_title_bonus_is_once_not_per_term_or_occurrence(self):
        weights = MatchWeights(technical_field=0, work_type=0, keyword=0, category=0, title=2, recent=0)
        result = match([RELATED], weights=weights)[0]
        self.assertEqual(result.score, 2)
        self.assertEqual(result.reasons[0].terms, ('ip-r&d', '반도체', '특허분석'))

    def test_generic_title_words_and_years_do_not_count(self):
        notice = {**NOTICE, 'title': '2026년 사업 공고 용역 모집'}
        record = Performance(performance_id='G', project_name='2026년 사업 공고 용역 모집')
        self.assertEqual(match([record], notice=notice)[0].score, 0)

    def test_work_type_uses_participation_type_when_exactly_applicable(self):
        notice = {'category': '', 'participation_type': '협력기관', 'keywords': [], 'title': '', 'summary': ''}
        record = Performance(performance_id='W', project_name='과제', work_type='협력기관')
        self.assertEqual(match([record], notice=notice)[0].score, 5)

    def test_category_exact_equality_and_configured_relation(self):
        notice = {'category': 'IP-R&D', 'participation_type': '', 'keywords': [], 'title': '', 'summary': ''}
        weights = MatchWeights(technical_field=0, work_type=0, keyword=0, title=0, recent=0)
        for value in ('IP-R&D', '특허분석'):
            record = Performance(performance_id='C', project_name='과제', work_type=value)
            self.assertEqual(match([record], notice=notice, weights=weights)[0].score, 3)
        other = Performance(performance_id='C', project_name='과제', work_type='설계')
        self.assertEqual(match([other], notice=notice, weights=weights)[0].score, 0)

    def test_category_bonus_once_even_multiple_relations_and_groups_match(self):
        weights = MatchWeights(technical_field=0, work_type=0, keyword=0, title=0, recent=0)
        result = match([RELATED], weights=weights, category_groups=(('IP-R&D', '특허분석'), ('IP-R&D', '특허분석')))[0]
        self.assertEqual(result.score, 3)

    def test_custom_or_disabled_category_relations(self):
        record = replace(UNRELATED, work_type='새업무')
        notice = {**NOTICE, 'category': '새분류'}
        self.assertEqual(match([record], notice=notice)[0].score, 0)
        self.assertEqual(match([record], notice=notice, category_groups=(('새분류', '새업무'),))[0].score, 3)
        without_exact_keyword = replace(RELATED, keywords=[])
        self.assertNotIn('category', [reason.rule for reason in match([without_exact_keyword], category_groups=())[0].reasons])

    def test_recent_window_includes_current_and_two_prior_years_only(self):
        for year, score in ((2026, 1), (2025, 1), (2024, 1), (2023, 0), (2027, 0), (None, 0)):
            with self.subTest(year=year):
                result = match([replace(UNRELATED, year=year)])[0]
                self.assertEqual(result.score, score)
                self.assertEqual(result.matched_terms, ())

    def test_recent_window_custom_and_disabled(self):
        record = replace(UNRELATED, year=2025)
        self.assertEqual(match([record], recent_years=1)[0].score, 0)
        self.assertEqual(match([record], recent_years=2)[0].score, 1)
        self.assertEqual(match([record], recent_years=0)[0].score, 0)

    def test_ties_use_id_ascending_not_input_order_or_recency(self):
        records = [replace(UNRELATED, performance_id='Z'), replace(UNRELATED, performance_id='A', year=1999)]
        self.assertEqual([r.performance_id for r in match(records)], ['A', 'Z'])
        self.assertEqual(match(records), match(reversed(records)))

    def test_top_n_default_zero_large_and_exact_prefix(self):
        records = [replace(UNRELATED, performance_id=f'P{i:03}') for i in range(8)]
        self.assertEqual(len(match(records)), 5)
        self.assertEqual(len(match(records, top_n=3)), 3)
        self.assertEqual(match(records, top_n=0), [])
        self.assertEqual(len(match(records, top_n=99)), 8)
        self.assertEqual(match(records, top_n=3), match(records, top_n=99)[:3])

    def test_empty_performance_iterable_returns_empty(self):
        self.assertEqual(match([]), [])

    def test_weights_customization_and_zero_disables_rules(self):
        result = match([RELATED], weights=MatchWeights(keyword=4, title=0))[0]
        self.assertEqual(result.score, 26)
        self.assertNotIn('title', [reason.rule for reason in result.reasons])
        disabled = MatchWeights(0, 0, 0, 0, 0, 0)
        result = match([RELATED], weights=disabled)[0]
        self.assertEqual((result.score, result.matched_terms, result.reasons), (0, (), ()))

    def test_inputs_are_not_mutated_and_results_are_json_ready_without_private_fields(self):
        notice = copy.deepcopy(NOTICE)
        before = copy.deepcopy(notice)
        result = match([RELATED], notice=notice)[0]
        self.assertEqual(notice, before)
        payload = result.to_dict()
        text = json.dumps(payload, ensure_ascii=False)
        for marker in ('private-client-marker', 'private-attorney-marker', 'private-notes-marker'):
            self.assertNotIn(marker, text)
        self.assertIsInstance(payload['matched_terms'], list)
        self.assertEqual(payload['score'], sum(item['points'] for item in payload['reasons']))

    def test_duplicate_ids_rejected_even_if_identical(self):
        for records in ([RELATED, RELATED], [RELATED, replace(RELATED, project_name='다른 실적')]):
            with self.assertRaisesRegex(MatchInputError, 'DUPLICATE_PERFORMANCE_ID'):
                match(records)

    def test_bad_inputs_fail_with_fixed_safe_diagnostics(self):
        for year in (None, 0, True, 2026.0, '2026'):
            with self.subTest(year=year), self.assertRaises(MatchInputError):
                match_notice(NOTICE, [], reference_year=year)
        for kwargs in ({'top_n': -1}, {'top_n': True}, {'weights': {}}, {'recent_years': -1},
                       {'category_groups': 'not groups'}, {'category_groups': ('not a group',)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(MatchInputError):
                match([], **kwargs)
        for notice in ({}, {**NOTICE, 'keywords': 'private-marker'}, {**NOTICE, 'keywords': [None]},
                       {**NOTICE, 'title': None}, {**NOTICE, 'summary': '\ud800'}):
            with self.assertRaises(MatchInputError) as error:
                match([], notice=notice)
            self.assertNotIn('private-marker', str(error.exception))
        for records in (None, [{}]):
            with self.assertRaises(MatchInputError):
                match(records)
        for kwargs in ({'keyword': -1}, {'keyword': True}, {'keyword': 2.0}):
            with self.assertRaises(MatchInputError):
                MatchWeights(**kwargs)


class MatcherIntegrationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent, prefix='matcher-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = PerformanceStore(self.root/'performance.db')
        blocker = patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('network forbidden'))
        blocker.start()
        self.addCleanup(blocker.stop)

    def test_empty_database_returns_empty(self):
        self.assertEqual(match_store(NOTICE, self.store, reference_year=2026), [])

    def test_database_matching_reads_beyond_search_default_100_and_is_read_only(self):
        for index in range(105):
            self.store.create(replace(UNRELATED, performance_id=f'U{index:03}', year=2026))
        self.store.create(replace(RELATED, year=2000))
        before = self.store.path.read_bytes()
        results = match_store(NOTICE, self.store, reference_year=2026, top_n=3)
        self.assertEqual((results[0].performance_id, results[0].score), ('P001', 21))
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_m12_feed_cache_and_sqlite_local_end_to_end_with_network_and_gemini_forbidden(self):
        stamp = '2026-11-02T01:00:00Z'
        internal = Notice(
            notice_id='N1', source_id='S1', institution='기관', title=NOTICE['title'],
            content_text=NOTICE['summary'], content_hash='hash', url='https://example.test/1',
            first_seen_at=stamp, last_seen_at=stamp, updated_at=stamp,
            gemini=GeminiResult(status='SUCCESS', analysis_policy='patent-firm-participation-v2', relevant=True, category=NOTICE['category'],
                                participation_type=NOTICE['participation_type'], keywords=NOTICE['keywords'],
                                reason='수행 가능', analyzed_at=stamp, analyzed_content_hash='hash'))
        feed = build_feed([internal], generated_at=stamp)
        metadata = {'schema_version': 2, 'generated_at': stamp, 'notice_count': 1}
        client = FeedClient('https://example.test/', cache_dir=self.root/'cache',
                            transport=lambda url, timeout: json.dumps(metadata if url.endswith('metadata.json') else feed).encode())
        client.sync()
        self.store.create(RELATED)
        before_cache, before_db = client.cache_path.read_bytes(), self.store.path.read_bytes()
        with patch('src.local_client.sync.FeedClient.sync', side_effect=AssertionError('sync forbidden')), \
             patch('src.ai.gemini.GeminiClient.generate', side_effect=AssertionError('Gemini forbidden')):
            cached_notice = client.load_cache()['feed']['notices'][0]
            result = match_store(cached_notice, self.store, reference_year=2026)[0]
        self.assertEqual(result.score, 22)
        self.assertEqual(client.cache_path.read_bytes(), before_cache)
        self.assertEqual(self.store.path.read_bytes(), before_db)

    def test_database_error_propagates_instead_of_empty_recommendations(self):
        self.store.path.unlink()
        with self.assertRaises(PerformanceDatabaseError):
            match_store(NOTICE, self.store, reference_year=2026)
        self.assertFalse(self.store.path.exists())


if __name__ == '__main__':
    unittest.main()
