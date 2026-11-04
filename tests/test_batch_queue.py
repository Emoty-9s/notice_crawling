"""No-provider regression of prefilter, durable work, batches and recovery."""
import copy
import io
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from src.ai.gemini import GeminiClient, GeminiError, parse_batch, parse_decision, api_error, load_policy
from src.ai.prefilter import Prefilter, POLICY_PATH
from src.ai.work_queue import BatchSession, RunLimits, prepare, due, order_queue, bounded_payload, queue_statistics
from src.core.analysis_state import AnalysisState
from src.core.eligibility import ANALYSIS_POLICY, current_analysis
from src.core.models import Notice, GeminiResult
from src.core.storage import JsonStorage, StorageIOError
from src.core.state_lock import state_writer
from src.renderer.feed import build_feed
from src.local_client.sync import validate_pair

NOW = datetime(2026,11,4,3,tzinfo=timezone.utc)
STAMP = NOW.isoformat()


def notice(identity='n', title='특허분석 용역 수행기관 모집', body=None, **changes):
    value = Notice(notice_id=identity,source_id='s',institution='합성 기관',title=title,
        content_text=body if body is not None else title+' 전문 수행기관의 자격과 용역 내용을 안내합니다.',
        content_hash=identity,url='https://example.test/'+identity,
        first_seen_at=STAMP,last_seen_at=STAMP,updated_at=STAMP)
    return replace(value,**changes)


def decision(identity='n', **changes):
    return dict(notice_id=identity,relevant=True,category='IP',participation_type='수행기관',
                reason='공개 특허분석 용역',keywords=['특허'],**changes)


class FakeBatch:
    policy = load_policy()
    last_usage = {}
    def __init__(self, responses=None):
        self.requests = []
        self.responses = list(responses or [])
    def generate_batch(self, records):
        self.requests.append(copy.deepcopy(records))
        response = self.responses.pop(0) if self.responses else {'results':[decision(r['notice_id']) for r in records]}
        if isinstance(response,BaseException): raise response
        return response if isinstance(response,str) else json.dumps(response)


class PrefilterTests(unittest.TestCase):
    def setUp(self): self.prefilter = Prefilter()

    def test_related_work_cases(self):
        for text in ('특허분석 용역','IP-R&D 수행기관 모집','기술사업화 전략 용역','선행기술조사',
                     '기술가치평가 용역','특허 라이선싱','FTO 분석','기술동향 분석','연구개발 과제 기획'):
            with self.subTest(text=text): self.assertEqual(self.prefilter.classify(notice(title=text))[0],'CANDIDATE')

    def test_unrelated_cases(self):
        for text in ('일반 인재양성 교육생 모집','대학생 취업캠프','일반 사무용 책상 구매',
                     '컴퓨터 장비 구매','일반 데이터 분석 서버 구매','홍보 전략 영상 제작',
                     '직원 만족도 조사','청소 용역 계약'):
            with self.subTest(text=text): self.assertEqual(self.prefilter.classify(notice(title=text))[0],'CLEARLY_UNRELATED')

    def test_mixed_cases_are_never_excluded(self):
        for text in ('특허 전문인력 양성 및 기업 특허 컨설팅 수행기관 모집',
                     '기술사업화 교육 및 기술이전 컨설팅 수행기관 모집','IP-R&D 전문가 인재양성 및 특허전략 지원',
                     '기술사업화 전문인력 양성','특허지원사업 수혜기업 모집','특허분석 및 서버 구매'):
            with self.subTest(text=text): self.assertIn(self.prefilter.classify(notice(title=text))[0],('CANDIDATE','REVIEW'))

    def test_missing_and_image_body_are_review(self):
        for body in ('','자료 확인','[이미지 본문: 텍스트 미추출, OCR 미수행] https://example.test/a.png'):
            self.assertEqual(self.prefilter.classify(notice(title='전문 용역 수행기관 모집',body=body))[0],'REVIEW')
            self.assertEqual(self.prefilter.classify(notice(title='청소 용역 계약',body=body))[0],'REVIEW')

    def test_ip_has_word_boundaries(self):
        for text in ('gossip review friendship membership shipment','K-VIP 글로벌 지원','YIP 교육'):
            self.assertEqual(self.prefilter.classify(notice(title=text))[0],'REVIEW')
        self.assertEqual(self.prefilter.classify(notice(title='IP 전략 수행기관'))[0],'CANDIDATE')

    def test_cache_content_and_configuration_change(self):
        first = self.prefilter.evaluate(notice(),STAMP)
        self.assertIs(self.prefilter.evaluate(first,(NOW+timedelta(days=1)).isoformat()),first)
        changed = self.prefilter.evaluate(replace(first,title='청소 용역',content_text='청소 용역 계약의 세부 자격 조건과 수행 내용을 공고합니다.'),STAMP)
        self.assertNotEqual(changed.analysis.prefilter_content_hash,first.analysis.prefilter_content_hash)
        self.assertEqual(changed.analysis.prefilter_status,'CLEARLY_UNRELATED')
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as root:
            path = Path(root)/'policy.json';policy=json.loads(POLICY_PATH.read_text(encoding='utf-8'))
            policy['version'] += 1;path.write_text(json.dumps(policy),encoding='utf-8')
            updated = Prefilter(path).evaluate(first,(NOW+timedelta(days=1)).isoformat())
        self.assertNotEqual(updated.analysis.prefilter_policy_version,first.analysis.prefilter_policy_version)


class BatchParsingTests(unittest.TestCase):
    def test_five_valid(self):
        self.assertEqual(len(parse_batch(json.dumps({'results':[decision(str(i)) for i in range(5)]}),map(str,range(5)))),5)

    def test_missing_duplicate_unknown_and_invalid_rows_preserve_other_results(self):
        rows=[decision('0'),decision('1'),decision('1'),decision('other'),dict(decision('2'),relevant=1),decision('3')]
        parsed=parse_batch(json.dumps({'results':rows}),map(str,range(5)))
        self.assertEqual(set(parsed),{'0','3'})

    def test_schema_fields_types_and_configured_enum(self):
        schema=load_policy()['output_schema'];schema['properties']['category']['enum']=['IP']
        for change in ({'category':12},{'participation_type':''},{'reason':None},{'keywords':['']},
                       {'relevant':1},{'category':'UNRECOGNIZED'}):
            rows=[dict(decision('n'),**change),decision('good')]
            self.assertEqual(set(parse_batch(json.dumps({'results':rows}),['n','good'],schema)),{'good'})
        with self.assertRaises(GeminiError): parse_batch('{bad',['n'])
        with self.assertRaises(GeminiError): parse_batch('[]',['n'])

    def test_strict_duplicate_json_keys(self):
        with self.assertRaises(GeminiError): parse_batch('{"results":[],"results":[]}',[])

    def test_real_client_batches_use_generatecontent_and_preserve_single_contract(self):
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.getcode.return_value=200
        response.read.return_value=json.dumps({'usageMetadata':{'promptTokenCount':12,'candidatesTokenCount':8},
            'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"results":[]}'}]}}]}).encode()
        opener=Mock(return_value=response)
        client=GeminiClient(api_key='synthetic-key',model='synthetic-model',opener=opener)
        from src.ai.gemini import notice_payload
        client.generate_batch([{'notice_id':'n',**notice_payload(notice())}])
        request=opener.call_args.args[0];body=json.loads(request.data)
        self.assertTrue(request.full_url.endswith(':generateContent'))
        self.assertEqual(body['contents'][0]['parts'][0]['text'],json.dumps({'notices':[{'notice_id':'n',**notice_payload(notice())}]},ensure_ascii=False))
        self.assertNotIn('synthetic-key',request.full_url)
        self.assertEqual(client.last_usage['promptTokenCount'],12)


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent);self.addCleanup(self.temp.cleanup)
        self.store=JsonStorage(Path(self.temp.name)/'state')
        self.now=NOW

    def run_queue(self, records, client=None, **options):
        session=BatchSession(client or FakeBatch(),limits=RunLimits(**options),clock=lambda:self.now)
        result=session.run(records,{'s'},self.store.save_notices)
        self.assertEqual(result,self.store.load_notices())
        return result,session

    def test_five_in_one_request_and_current_cache_reused(self):
        client=FakeBatch();result,session=self.run_queue([notice(str(i)) for i in range(5)],client)
        self.assertEqual((len(client.requests),session.metrics['successful_notices']),(1,5))
        self.assertTrue(all(current_analysis(n) for n in result))
        result,session=self.run_queue(result,client)
        self.assertEqual(len(client.requests),1);self.assertEqual(session.metrics['cache_hits'],5)

    def test_queue_enforces_configured_output_schema_enum(self):
        client=FakeBatch()
        client.policy=copy.deepcopy(load_policy())
        client.policy['output_schema']['properties']['category']['enum']=['ALLOWED_ONLY']
        result,session=self.run_queue([notice()],client,max_api_requests_per_run=1)
        self.assertEqual(result[0].analysis.analysis_status,'RETRY_WAIT')
        self.assertNotEqual(result[0].gemini.status,'SUCCESS')
        self.assertEqual(session.metrics['successful_notices'],0)

    def test_partial_missing_only_missing_is_pending_when_budget_ends(self):
        client=FakeBatch([{'results':[decision(str(i)) for i in range(4)]}])
        result,session=self.run_queue([notice(str(i)) for i in range(5)],client,max_api_requests_per_run=1)
        self.assertEqual(sum(current_analysis(n) for n in result),4)
        self.assertEqual(result[4].analysis.analysis_status,'RETRY_WAIT')
        self.assertEqual(session.metrics['api_requests'],1)
        self.now+=timedelta(minutes=6)
        result,_=self.run_queue(result,client)
        self.assertEqual([r['notice_id'] for r in client.requests[-1]],['4'])
        self.assertTrue(all(current_analysis(n) for n in result))

    def test_malformed_batch_shrinks_to_two_then_one(self):
        client=FakeBatch(['broken','broken'])
        result,session=self.run_queue([notice(str(i)) for i in range(5)],client)
        self.assertEqual([len(r) for r in client.requests[:3]],[5,2,1])
        self.assertEqual(session.metrics['successful_notices'],5)

    def test_single_fallback_can_use_preserved_generate_contract(self):
        class Dual(FakeBatch):
            singles=0
            def generate(self,payload):
                self.singles+=1
                value=decision();value.pop('notice_id')
                return json.dumps(value)
        client=Dual(['bad','bad'])
        result,session=self.run_queue([notice(str(i)) for i in range(5)],client)
        self.assertGreater(client.singles,0)
        self.assertTrue(all(current_analysis(n) for n in result))

    def test_invalid_single_is_retry_wait_not_irrelevant(self):
        result,session=self.run_queue([notice()],FakeBatch(['broken']))
        self.assertIsNone(result[0].gemini.relevant)
        self.assertEqual(result[0].analysis.analysis_status,'RETRY_WAIT')

    def test_max_batch_ten_and_request_budget_separate_from_notice_budget(self):
        client=FakeBatch();result,session=self.run_queue([notice(str(i)) for i in range(12)],client,batch_size=10,
            max_api_requests_per_run=1,max_notices_per_run=12)
        self.assertEqual(session.metrics['api_requests'],1)
        self.assertEqual(session.metrics['successful_notices'],10)
        self.assertEqual(len(client.requests[0]),10)
        result,session=self.run_queue([notice(str(i)) for i in range(12)],batch_size=5,max_notices_per_run=3)
        self.assertEqual(session.metrics['successful_notices'],3)

    def test_unrelated_and_expired_zero_calls_and_preserved_history(self):
        result,session=self.run_queue([notice('unrelated',title='일반 사무용 책상 구매'),notice('expired',apply_end='2020-01-01')])
        self.assertEqual(session.metrics['api_requests'],0);self.assertEqual(len(result),2)

    def test_hash_or_policy_changes_reanalyze_without_discarding_prior_success(self):
        first,_=self.run_queue([notice()]);old=first[0]
        for changed in (replace(old,content_hash='new'),replace(old,gemini=replace(old.gemini,analysis_policy='old'))):
            result,session=self.run_queue([changed])
            self.assertEqual(session.metrics['api_requests'],1)
            self.assertTrue(current_analysis(result[0]))
            self.assertEqual(result[0].analysis.previous_results,(changed.gemini,))

    def test_schema_change_reanalyzes_even_when_hash_and_policy_match(self):
        first,_=self.run_queue([notice()])
        with patch('src.core.eligibility.analysis_schema_fingerprint',return_value='new-schema'), \
             patch('src.ai.work_queue.ANALYSIS_SCHEMA_FINGERPRINT','new-schema'):
            result,session=self.run_queue(first)
            self.assertEqual(session.metrics['api_requests'],1)
            self.assertTrue(current_analysis(result[0]))
            self.assertEqual(result[0].analysis.result_schema_fingerprint,'new-schema')

    def test_503_bounded_retry_then_success(self):
        client=FakeBatch([GeminiError('API_ERROR',retryable=True,http_status=503)])
        result,session=self.run_queue([notice()],client)
        self.assertTrue(current_analysis(result[0]));self.assertEqual(session.metrics['retries'],1)
        self.assertEqual(session.metrics['http_503'],1)

    def test_503_repeated_opens_circuit_and_defers_remaining(self):
        error=GeminiError('API_ERROR',retryable=True,http_status=503)
        result,session=self.run_queue([notice(str(i)) for i in range(8)],FakeBatch([error]*3))
        self.assertEqual(session.metrics['api_requests'],3)
        self.assertEqual(session.stop_reason,'CIRCUIT_OPEN')
        self.assertEqual(sum(n.analysis.analysis_status=='RETRY_WAIT' for n in result),5)

    def test_timeout_after_retry_limit_resumes_next_run(self):
        result,session=self.run_queue([notice()],FakeBatch([TimeoutError()]*3))
        self.assertEqual(session.metrics['timeouts'],3)
        self.now+=timedelta(minutes=6)
        result,session=self.run_queue(result)
        self.assertTrue(current_analysis(result[0]))

    def test_429_honors_retry_after_and_stops_new_notices_next_run(self):
        client=FakeBatch([GeminiError('API_ERROR',retryable=True,http_status=429,retry_after=900,quota_scope='MINUTE')])
        result,session=self.run_queue([notice(str(i)) for i in range(8)],client)
        self.assertEqual(len(client.requests),1)
        self.assertTrue(all(n.analysis.analysis_status=='RETRY_WAIT' for n in result))
        self.assertTrue(all(datetime.fromisoformat(n.analysis.next_retry_at)>=NOW+timedelta(seconds=900) for n in result))
        self.now+=timedelta(seconds=60)
        result,session=self.run_queue([*result,notice('new')],client)
        self.assertEqual(len(client.requests),1);self.assertEqual(session.stop_reason,'RATE_LIMIT_COOLDOWN')
        self.now+=timedelta(minutes=20)
        result,session=self.run_queue(result,client)
        self.assertTrue(all(current_analysis(n) for n in result))

    def test_daily_and_zero_quota_wait_until_pacific_reset(self):
        for scope in ('DAILY','ZERO'):
            result,session=self.run_queue([notice()],FakeBatch([GeminiError('API_ERROR',retryable=True,http_status=429,quota_scope=scope,quota_limit=0)]))
            self.assertGreaterEqual(datetime.fromisoformat(result[0].analysis.next_retry_at),NOW.replace(hour=8))
            self.assertLess(datetime.fromisoformat(result[0].analysis.next_retry_at),NOW+timedelta(days=1))
            self.assertEqual(session.metrics['quota_limit'],0)

    def test_authentication_failure_is_permanent_operator_action(self):
        result,session=self.run_queue([notice()],FakeBatch([GeminiError('API_ERROR',http_status=403)]))
        self.assertEqual(result[0].analysis.analysis_status,'PERMANENT_FAILURE')
        self.assertEqual(session.stop_reason,'OPERATOR_ACTION')
        self.assertIsNone(result[0].gemini.relevant)

    def test_request_retry_token_and_runtime_budgets(self):
        error=GeminiError('API_ERROR',retryable=True,http_status=503)
        result,session=self.run_queue([notice()],FakeBatch([error]*3),max_api_requests_per_run=1)
        self.assertEqual(session.metrics['api_requests'],1)
        result,session=self.run_queue([notice()],max_input_tokens_per_run=1)
        self.assertEqual(session.metrics['api_requests'],0);self.assertEqual(session.stop_reason,'TOKEN_BUDGET')
        session=BatchSession(FakeBatch(),limits=RunLimits(max_run_seconds=1),clock=lambda:NOW,monotonic=Mock(side_effect=[0,2,2,2]))
        session.run([notice()],{'s'},self.store.save_notices)
        self.assertEqual(session.metrics['api_requests'],0);self.assertEqual(session.stop_reason,'TIME_BUDGET')

    def test_lease_survives_crash_and_expiry_recovers(self):
        class Crash(FakeBatch):
            def generate_batch(self,records): raise KeyboardInterrupt()
        session=BatchSession(Crash(),clock=lambda:NOW)
        with self.assertRaises(KeyboardInterrupt):session.run([notice()],{'s'},self.store.save_notices)
        claimed=self.store.load_notices()
        self.assertEqual(claimed[0].analysis.analysis_status,'IN_PROGRESS')
        result,session=self.run_queue(claimed)
        self.assertEqual(session.metrics['api_requests'],0)
        self.now+=timedelta(minutes=16)
        result,session=self.run_queue(claimed)
        self.assertTrue(current_analysis(result[0]))

    def test_success_checkpoint_survives_later_result_save_failure(self):
        checkpoints=[]
        def save(records):
            if sum(current_analysis(n) for n in records)>1: raise StorageIOError('INJECTED')
            self.store.save_notices(records);checkpoints.append(records)
        with self.assertRaises(StorageIOError):
            BatchSession(FakeBatch(),clock=lambda:NOW).run([notice('a'),notice('b')],{'s'},save)
        stored=self.store.load_notices()
        self.assertEqual(sum(current_analysis(n) for n in stored),1)
        self.assertEqual(sum(n.analysis.analysis_status=='IN_PROGRESS' for n in stored),1)

    def test_claim_save_failure_prevents_api_call(self):
        client=FakeBatch()
        def fail(records): raise StorageIOError('INJECTED')
        with self.assertRaises(StorageIOError):BatchSession(client,clock=lambda:NOW).run([notice()],{'s'},fail)
        self.assertEqual(client.requests,[])

    def test_single_writer_lock_rejects_overlap_and_releases(self):
        with state_writer(self.store.data_dir):
            with self.assertRaisesRegex(ValueError,'CENTRAL_WRITER_BUSY'):
                with state_writer(self.store.data_dir): pass
        with state_writer(self.store.data_dir): pass

    def test_old_notice_without_queue_loads_without_rewriting(self):
        self.store.data_dir.mkdir()
        record=notice().to_dict();record.pop('analysis')
        self.store.notices_path.write_text(json.dumps([record]),encoding='utf-8')
        before=self.store.notices_path.read_bytes()
        self.assertEqual(self.store.load_notices()[0].analysis,AnalysisState())
        self.assertEqual(self.store.notices_path.read_bytes(),before)

    def test_priority_and_review_aging(self):
        p=Prefilter()
        candidate=prepare(notice('new'),p,NOW)
        updated=prepare(notice('changed',status='UPDATED'),p,NOW)
        review=prepare(notice('review',title='모호한 전문 용역',first_seen_at=(NOW-timedelta(days=10)).isoformat()),p,NOW)
        ordered=order_queue([review,updated,candidate],NOW)
        self.assertLess(ordered.index(candidate),ordered.index(updated))
        self.assertIn(review,ordered[:4])

    def test_large_bodies_are_bounded_and_batch_shrinks(self):
        n=notice(body='처음'+'a'*20000+'\n참가자격 특허법인\n'+'b'*20000+'끝')
        payload=bounded_payload(n,12000)
        self.assertIn('참가자격',payload['content_text']);self.assertIn('처음',payload['content_text']);self.assertIn('끝',payload['content_text'])
        client=FakeBatch();result,session=self.run_queue([replace(n,notice_id=str(i)) for i in range(3)],client,max_batch_input_tokens=12000)
        self.assertTrue(all(len(r)==1 for r in client.requests))

    def test_provider_payload_redacts_contacts_but_preserves_requirements_dates(self):
        value=bounded_payload(notice(body='참가자격: 특허법인. 마감 2026-11-30. 담당자: 홍길동, 연락 010-1234-5678, contact@example.test'),12000)
        text=value['content_text']
        self.assertNotIn('홍길동',text);self.assertNotIn('010-1234-5678',text);self.assertNotIn('contact@example.test',text)
        self.assertIn('특허법인',text);self.assertIn('2026-11-30',text)

    def test_progressive_feed_preserves_successes_when_another_batch_fails(self):
        success,_=self.run_queue([notice('cached')])
        error=GeminiError('API_ERROR',retryable=True,http_status=429)
        client=FakeBatch([{'results':[decision('a')]},error])
        result,session=self.run_queue([*success,notice('a'),notice('b')],client,batch_size=1)
        feed=build_feed(result,generated_at=STAMP)
        self.assertEqual({n['notice_id'] for n in feed['notices']},{'cached','a','b'})
        validate_pair(feed,dict(schema_version=3,generated_at=feed['generated_at'],notice_count=3))
        stats=queue_statistics(result,NOW)
        self.assertEqual(stats['public_eligible'],3);self.assertEqual(stats['analysis_status'],'PARTIAL')

    def test_bad_limits_rejected(self):
        for change in ({'batch_size':11},{'batch_size':True},{'max_api_requests_per_run':0},{'max_retries':8}):
            with self.assertRaises(ValueError): RunLimits(**change)

    def test_real_provider_spacing_backoff_and_usage_with_injected_time(self):
        ticks=[0.0];starts=[];sleeps=[]
        class Provider(GeminiClient):
            def __init__(self):
                self.timeout=1;self.policy=load_policy();self.last_usage={};self.model='gemini-synthetic'
            def generate_batch(self,records):
                starts.append(ticks[0])
                if len(starts)==1: raise GeminiError('API_ERROR',retryable=True,http_status=503)
                self.last_usage={'promptTokenCount':10,'candidatesTokenCount':5}
                return json.dumps({'results':[decision(r['notice_id']) for r in records]})
        def sleep(seconds):sleeps.append(seconds);ticks[0]+=seconds
        session=BatchSession(Provider(),limits=RunLimits(batch_size=1),clock=lambda:NOW+timedelta(seconds=ticks[0]),
                             monotonic=lambda:ticks[0],sleep=sleep,jitter=lambda:0)
        result=session.run([notice('a'),notice('b')],{'s'},self.store.save_notices)
        self.assertEqual(starts,[0,6,12]);self.assertEqual(sleeps,[2,4,6])
        self.assertEqual(session.metrics['input_tokens'],20);self.assertEqual(session.metrics['output_tokens'],10)
        self.assertTrue(all(current_analysis(n) for n in result))

    def test_duplicate_input_refused_without_writing(self):
        client=FakeBatch()
        with self.assertRaisesRegex(ValueError,'DUPLICATE_NOTICE_ID'):
            self.run_queue([notice(),notice()],client)
        self.assertEqual(client.requests,[]);self.assertFalse(self.store.notices_path.exists())


class ErrorDetailTests(unittest.TestCase):
    def test_quota_details_retryinfo_and_safe_redaction(self):
        raw=json.dumps({'error':{'message':'secret must not survive limit: 0','details':[
            {'@type':'type.googleapis.com/google.rpc.QuotaFailure','violations':[{'quotaId':'GenerateRequestsPerDay','quotaValue':'0'}]},
            {'@type':'type.googleapis.com/google.rpc.RetryInfo','retryDelay':'60.5s'}]}}).encode()
        error=api_error(429,{'Retry-After':'120'},raw,now=NOW)
        self.assertEqual((error.retry_after,error.quota_scope,error.quota_limit),(120,'ZERO',0))
        self.assertNotIn('secret',str(error)+repr(error.__dict__))

    def test_retry_after_http_date_and_unknown_quota(self):
        error=api_error(429,{'Retry-After':'Wed, 04 Nov 2026 03:10:00 GMT'},b'bad',now=NOW)
        self.assertEqual(error.retry_after,600);self.assertEqual(error.quota_scope,'UNKNOWN')

    def test_http_client_extracts_error_and_closes_body(self):
        body=io.BytesIO(b'{"error":{"details":[],"message":"quota limit: 0"}}')
        opener=Mock(side_effect=HTTPError('https://example.test',429,'secret',{'Retry-After':'90'},body))
        client=GeminiClient(api_key='synthetic',model='model',opener=opener)
        from src.ai.gemini import notice_payload
        with self.assertRaises(GeminiError) as caught:client.generate(notice_payload(notice()))
        self.assertEqual(caught.exception.retry_after,90);self.assertEqual(caught.exception.quota_limit,0)
        self.assertTrue(body.closed)
