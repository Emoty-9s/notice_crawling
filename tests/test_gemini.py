"""M08 mock-only Gemini, cache, error isolation and persistence compatibility."""

import contextlib
import io
import json
import logging
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from src.ai.gemini import GeminiClient, GeminiError, INPUT_FIELDS, load_policy, notice_payload, parse_decision
from src.ai.relevance import RelevanceAnalyzer
from src.core.diff import compare_notice
from src.core.models import GeminiResult, GeminiStatus, Notice
from src.core.storage import JsonStorage, StorageSchemaError


NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)
KEY = 'unit-test-secret-never-log'
MODEL = 'explicit-test-model'


def notice(identifier='one', **overrides):
    fields = dict(
        notice_id=identifier, source_id='example', institution='한국특허전략개발원',
        title='특허분석 협력기관 모집', url='https://example.test/notice',
        content_text='특허법인/특허사무소가 특허분석 협력기관으로 참여 가능', content_hash='hash-1',
        first_seen_at='2026-10-29T00:00:00Z', last_seen_at='2026-10-29T00:00:00Z',
        updated_at='2026-10-29T00:00:00Z',
    )
    fields.update(overrides)
    return Notice(**fields)


def decision(relevant=True, **overrides):
    fields = dict(relevant=relevant, category='IP-R&D', participation_type='협력기관',
                  reason='특허법인이 특허분석 협력기관으로 참여할 수 있음', keywords=['반도체', '특허분석'])
    fields.update(overrides)
    return fields


def response(payload=None, *, text=None, finish='STOP'):
    data = payload if payload is not None else {
        'candidates': [{'finishReason': finish, 'content': {'parts': [
            {'text': text if text is not None else json.dumps(decision(), ensure_ascii=False)}]}}]}
    fake = Mock()
    fake.getcode.return_value = 200
    fake.read.return_value = json.dumps(data, ensure_ascii=False).encode('utf-8')
    fake.__enter__ = Mock(return_value=fake)
    fake.__exit__ = Mock(return_value=False)
    return fake


def fake_analyzer(*responses):
    client = Mock()
    client.generate.side_effect = list(responses) or [json.dumps(decision(), ensure_ascii=False)]
    analyzer = RelevanceAnalyzer(client, clock=lambda: NOW, logger=Mock(spec=logging.Logger))
    return analyzer, client


class GeminiClientTests(unittest.TestCase):
    def test_mock_rest_request_and_structured_response(self):
        opener = Mock(return_value=response())
        client = GeminiClient(api_key=KEY, model=MODEL, timeout=7, opener=opener)
        parsed = parse_decision(client.generate(notice_payload(notice())))
        self.assertIs(parsed['relevant'], True)
        request = opener.call_args.args[0]
        self.assertNotIn(KEY, request.full_url)
        self.assertEqual(request.get_header('X-goog-api-key'), KEY)
        self.assertEqual(request.method, 'POST')
        self.assertEqual(opener.call_args.kwargs, {'timeout': 7})
        body = json.loads(request.data)
        self.assertEqual(set(json.loads(body['contents'][0]['parts'][0]['text'])['notice_data']), set(INPUT_FIELDS))
        self.assertEqual(body['generationConfig']['responseFormat']['text']['mimeType'], 'APPLICATION_JSON')
        self.assertEqual(set(body['generationConfig']['responseFormat']['text']['schema']['required']), set(decision()))
        self.assertNotIn('score', body['generationConfig']['responseFormat']['text']['schema']['properties'])
        self.assertNotIn('tools', body)
        opener.return_value.__exit__.assert_called_once()

    def test_policy_boundaries_and_minimal_input(self):
        policy = load_policy()
        rules = ' '.join(policy['rules'])
        for token in ('특허법인', '수혜기업', '실적', '불명확', '신뢰할 수 없는'):
            self.assertIn(token, rules)
        payload = notice_payload(notice())
        self.assertEqual(tuple(payload), INPUT_FIELDS)
        for forbidden in ('gemini', 'notice_id', 'content_hash', 'performance', 'customer'):
            self.assertNotIn(forbidden, payload)

    def test_true_false_and_uncertain_decisions(self):
        for relevant, participation in ((True, '협력기관'), (False, '수혜기업'), (False, '불명확')):
            with self.subTest(relevant=relevant, participation=participation):
                payload = decision(relevant, participation_type=participation)
                self.assertEqual(parse_decision(json.dumps(payload)), payload)

    def test_malformed_json_and_strict_schema(self):
        invalid = ['not json', '```json\n{}\n```', 'null', '[]', '{"relevant":true,"relevant":false}', 'NaN']
        invalid += [json.dumps(payload) for payload in (
            {**decision(), 'relevant': 'true'}, {**decision(), 'relevant': 1},
            {**decision(), 'participation_type': None}, {**decision(), 'reason': ' '},
            {**decision(), 'keywords': '특허'}, {**decision(), 'keywords': [42]},
            {**decision(), 'extra': 'not allowed'}, {k:v for k,v in decision().items() if k != 'keywords'},
        )]
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(GeminiError):
                parse_decision(text)

    def test_timeout_and_api_errors_are_sanitized(self):
        errors = [TimeoutError(KEY), URLError(KEY), HTTPError('https://example.test/?key='+KEY, 429, KEY, {}, None),
                  HTTPError('https://example.test/?key='+KEY, 403, KEY, {}, None)]
        for error in errors:
            with self.subTest(error=type(error).__name__):
                client = GeminiClient(api_key=KEY, model=MODEL, opener=Mock(side_effect=error))
                with self.assertRaises(GeminiError) as context:
                    client.generate(notice_payload(notice()))
                self.assertNotIn(KEY, str(context.exception))
                self.assertTrue(context.exception.__suppress_context__)

    def test_missing_config_makes_no_request(self):
        for key, model in (('', MODEL), (KEY, ''), (KEY, '../wrong'), ('bad\nkey', MODEL)):
            opener = Mock()
            client = GeminiClient(api_key=key, model=model, opener=opener)
            with self.assertRaises(GeminiError) as context:
                client.generate(notice_payload(notice()))
            self.assertTrue(context.exception.retryable)
            opener.assert_not_called()

    def test_blocked_truncated_and_invalid_api_envelopes(self):
        invalid = [{}, {'error': {'message': KEY}}, {'promptFeedback': {'blockReason': 'SAFETY'}},
                   {'candidates': []}, {'candidates': [None]}, {'candidates': [{'finishReason': 'MAX_TOKENS'}]}]
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(GeminiError):
                GeminiClient(api_key=KEY, model=MODEL, opener=Mock(return_value=response(payload))).generate(notice_payload(notice()))
        with self.assertRaises(GeminiError):
            GeminiClient(api_key=KEY, model=MODEL, opener=Mock(return_value=response(finish='SAFETY'))).generate(notice_payload(notice()))

    def test_invalid_timeout_and_policy_fail_without_network(self):
        for timeout in (0, -1, float('nan'), True):
            with self.subTest(timeout=timeout), self.assertRaises(GeminiError):
                GeminiClient(timeout=timeout)
        with self.assertRaises(GeminiError):
            load_policy(Path(__file__).parent/'no-such-policy.json')


class RelevanceTests(unittest.TestCase):
    def test_success_stores_participation_keywords_and_analyzed_hash(self):
        analyzer, client = fake_analyzer()
        original = notice()
        result = analyzer.analyze(original)
        self.assertIs(result.gemini.status, GeminiStatus.SUCCESS)
        self.assertIs(result.gemini.relevant, True)
        self.assertEqual(result.gemini.participation_type, '협력기관')
        self.assertEqual(result.gemini.keywords, ('반도체', '특허분석'))
        self.assertEqual(result.gemini.analyzed_content_hash, result.content_hash)
        self.assertEqual(result.gemini.analyzed_at, NOW.isoformat())
        self.assertIsNone(result.gemini.score)
        self.assertEqual(Notice.from_json(result.to_json()), result)
        self.assertIs(original.gemini.status, GeminiStatus.NOT_ANALYZED)
        client.generate.assert_called_once()

    def test_irrelevant_false_is_stored_as_success(self):
        analyzer, _ = fake_analyzer(json.dumps(decision(False, participation_type='수혜기업', reason='수혜기업만 신청')))
        result = analyzer.analyze(notice())
        self.assertIs(result.gemini.status, GeminiStatus.SUCCESS)
        self.assertIs(result.gemini.relevant, False)

    def test_same_hash_repeated_input_calls_once(self):
        analyzer, client = fake_analyzer()
        first = analyzer.analyze(notice())
        second = analyzer.analyze(notice())
        self.assertEqual(second.gemini, first.gemini)
        self.assertEqual(client.generate.call_count, 1)

    def test_persisted_success_reused_by_new_analyzer(self):
        analyzer, _ = fake_analyzer()
        stored = Notice.from_json(analyzer.analyze(notice()).to_json())
        next_analyzer, client = fake_analyzer()
        result = next_analyzer.analyze(replace(stored, status='UPDATED', title='제목만 수정'))
        self.assertEqual(result.gemini, stored.gemini)
        client.generate.assert_not_called()

    def test_changed_hash_reanalysis_uses_m07_preserved_result(self):
        analyzer, client = fake_analyzer(json.dumps(decision()), json.dumps(decision(False)))
        old = analyzer.analyze(notice())
        diff = compare_notice(notice(content_text='수혜기업만 참여', content_hash='hash-2'), old, observed_at=NOW.isoformat())
        self.assertEqual(diff.notice.gemini, old.gemini)
        result = analyzer.analyze(diff.notice)
        self.assertEqual(client.generate.call_count, 2)
        self.assertIs(result.gemini.relevant, False)
        self.assertEqual(result.gemini.analyzed_content_hash, 'hash-2')

    def test_existing_never_calls_even_for_failed_pending_or_missing_analysis(self):
        for status in GeminiStatus:
            analyzer, client = fake_analyzer()
            original = notice(status='EXISTING', gemini=GeminiResult(status=status))
            result = analyzer.analyze(original)
            self.assertIs(result.gemini.status, GeminiStatus.PENDING if status == GeminiStatus.NOT_ANALYZED else status)
            client.generate.assert_not_called()

    def test_hash_cache_is_scoped_by_notice_identity(self):
        analyzer, client = fake_analyzer(json.dumps(decision()), json.dumps(decision(False)))
        result = analyzer.analyze_batch([notice('one'), notice('two')])
        self.assertEqual(client.generate.call_count, 2)
        self.assertNotEqual(result[0].gemini.relevant, result[1].gemini.relevant)

    def test_duplicate_batch_input_does_not_call_twice(self):
        analyzer, client = fake_analyzer()
        result = analyzer.analyze_batch([notice(), notice()])
        self.assertEqual(client.generate.call_count, 1)
        self.assertEqual(result[0].gemini, result[1].gemini)

    def test_malformed_response_is_failed_and_next_notice_continues(self):
        analyzer, client = fake_analyzer('broken', json.dumps(decision()))
        result = analyzer.analyze_batch([notice('bad'), notice('good')])
        self.assertEqual([n.gemini.status for n in result], [GeminiStatus.FAILED, GeminiStatus.SUCCESS])
        self.assertEqual(analyzer.errors['bad'], 'MALFORMED_JSON')
        self.assertEqual(client.generate.call_count, 2)

    def test_timeout_quota_and_missing_configuration_are_pending(self):
        for error in (TimeoutError(KEY), GeminiError('API_ERROR', retryable=True),
                      GeminiError('MISSING_OR_INVALID_CONFIGURATION', retryable=True)):
            analyzer, client = fake_analyzer(error)
            result = analyzer.analyze(notice())
            self.assertIs(result.gemini.status, GeminiStatus.PENDING)
            self.assertIsNone(result.gemini.analyzed_content_hash)

    def test_failed_reanalysis_keeps_prior_judgment_and_successful_hash(self):
        first, _ = fake_analyzer()
        old = first.analyze(notice())
        analyzer, client = fake_analyzer(RuntimeError(KEY))
        result = analyzer.analyze(replace(old, status='UPDATED', content_hash='changed'))
        self.assertIs(result.gemini.status, GeminiStatus.FAILED)
        self.assertEqual(result.gemini.reason, old.gemini.reason)
        self.assertEqual(result.gemini.participation_type, old.gemini.participation_type)
        self.assertEqual(result.gemini.analyzed_content_hash, old.content_hash)
        self.assertEqual(result.gemini.analyzed_at, old.gemini.analyzed_at)

    def test_failed_attempt_is_memoized_within_session(self):
        analyzer, client = fake_analyzer(TimeoutError())
        results = analyzer.analyze_batch([notice(), notice()])
        self.assertTrue(all(n.gemini.status == GeminiStatus.PENDING for n in results))
        self.assertEqual(client.generate.call_count, 1)

    def test_secret_not_in_errors_logs_or_console(self):
        stream = io.StringIO()
        logger = logging.getLogger('gemini-secret-test')
        handler = logging.StreamHandler(stream)
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)
        client = GeminiClient(api_key=KEY, model=MODEL, opener=Mock(side_effect=HTTPError('https://example.test/?key='+KEY, 403, KEY, {}, None)))
        analyzer = RelevanceAnalyzer(client, clock=lambda: NOW, logger=logger)
        console = io.StringIO()
        with contextlib.redirect_stdout(console), contextlib.redirect_stderr(console):
            result = analyzer.analyze(notice())
        self.assertIs(result.gemini.status, GeminiStatus.FAILED)
        self.assertNotIn(KEY, stream.getvalue()+console.getvalue()+repr(analyzer.errors)+result.to_json()+repr(client))

    def test_unrecognized_error_code_cannot_leak_raw_secret(self):
        error = GeminiError(KEY)
        self.assertEqual(str(error), 'ANALYSIS_ERROR')
        analyzer, _ = fake_analyzer(error)
        result = analyzer.analyze(notice())
        self.assertIs(result.gemini.status, GeminiStatus.FAILED)
        self.assertEqual(analyzer.errors, {'one': 'ANALYSIS_ERROR'})
        self.assertNotIn(KEY, repr(analyzer.logger.warning.call_args))

    def test_keywords_are_immutable_and_wrong_types_rejected(self):
        values = ['특허']
        model = GeminiResult(participation_type='수행기관', keywords=values)
        values.append('외부 수정')
        self.assertEqual(model.keywords, ('특허',))
        with self.assertRaises(FrozenInstanceError):
            model.keywords = ()
        for value in ('특허', [None], [1], [' ']):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                GeminiResult(keywords=value)


class GeminiPersistenceTests(unittest.TestCase):
    def setUp(self):
        tests_root = Path(__file__).resolve().parent
        temp = tempfile.TemporaryDirectory(dir=tests_root, prefix='gemini-test-')
        self.root = Path(temp.name).resolve()
        if self.root.parent != tests_root or not self.root.name.startswith('gemini-test-'):
            raise RuntimeError('unexpected cleanup target')
        self.addCleanup(temp.cleanup)
        self.storage = JsonStorage(self.root)

    def test_full_structured_result_storage_round_trip(self):
        analyzer, _ = fake_analyzer()
        saved = analyzer.analyze(notice())
        self.storage.save_notices([saved])
        restored = self.storage.load_notices()[0]
        self.assertEqual(restored, saved)
        self.assertEqual(restored.gemini.participation_type, '협력기관')
        self.assertEqual(restored.gemini.keywords, ('반도체', '특허분석'))
        analyzer, client = fake_analyzer()
        analyzer.analyze(replace(restored, status='EXISTING'))
        client.generate.assert_not_called()

    def test_legacy_eight_field_result_loads_without_rewriting_file(self):
        data = notice().to_dict()
        del data['gemini']['participation_type']
        del data['gemini']['keywords']
        text = json.dumps([data])
        self.storage.notices_path.write_text(text, encoding='utf-8')
        restored = self.storage.load_notices()[0]
        self.assertIsNone(restored.gemini.participation_type)
        self.assertIsNone(restored.gemini.keywords)
        self.assertEqual(self.storage.notices_path.read_text(encoding='utf-8'), text)

    def test_partial_new_schema_or_invalid_keywords_are_not_legacy(self):
        for mutate in ('missing_one_new_field', 'wrong_keywords'):
            data = notice().to_dict()
            if mutate == 'missing_one_new_field':
                del data['gemini']['keywords']
            else:
                data['gemini']['keywords'] = [True]
            self.storage.notices_path.write_text(json.dumps([data]), encoding='utf-8')
            with self.subTest(mutate=mutate), self.assertRaises(StorageSchemaError):
                self.storage.load_notices()


if __name__ == '__main__':
    unittest.main()
