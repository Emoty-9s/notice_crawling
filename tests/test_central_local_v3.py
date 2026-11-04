"""The v3 producer publishes conservative candidates, never AI judgments."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch
from src.renderer.feed import build_feed,write_feed
from src.core.models import Notice,GeminiResult
from src.core.analysis_state import AnalysisState
from src.local_client.sync import validate_pair,SyncError
from src.local_client.notice_analysis import LocalNoticeAnalysis,adapt_notice
from test_local_notice_analysis import Encoder

STAMP='2026-11-04T03:00:00Z'
def notice(identity='n',**changes):
    data=dict(notice_id=identity,source_id='kipa_bid',institution='공개 기관',title='배터리 특허분석 용역',
              content_text='참가 자격은 원문에서 확인합니다. 특허분석 전문 수행기관 선정 용역입니다.',
              content_hash='hash',url='https://example.test/'+identity,first_seen_at=STAMP,last_seen_at=STAMP,updated_at=STAMP)
    data.update(changes);return Notice(**data)

class CentralV3Tests(unittest.TestCase):
    def test_candidate_review_and_expired_retained_for_local_override_unrelated_hidden(self):
        records=[notice(),notice('review',title='전문 용역 모집',content_text=''),
                 notice('unrelated',title='청소 용역 계약',content_text='청소 용역 계약의 시설 청소 세부 작업 사항입니다.'),
                 notice('expired',apply_end='2020-01-01')]
        before=[n.to_dict() for n in records]
        with patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('no provider')):
            feed=build_feed(records,generated_at=STAMP)
        self.assertEqual(feed['schema_version'],3)
        self.assertEqual({n['prefilter_status'] for n in feed['notices']},{'CANDIDATE','REVIEW'})
        self.assertEqual({n['notice_id'] for n in feed['notices']},{'n','review','expired'})
        self.assertEqual([n.to_dict() for n in records],before)
        validate_pair(feed,dict(schema_version=3,generated_at=STAMP,notice_count=3))

    def test_legacy_success_false_and_retry_future_do_not_control_publication(self):
        historical=notice(gemini=GeminiResult(status='SUCCESS',relevant=False,analysis_policy='old'),
                          analysis=AnalysisState(analysis_status='RETRY_WAIT',attempts=9,next_retry_at='2030-01-01T00:00:00Z'))
        before=historical.to_dict();feed=build_feed([historical],generated_at=STAMP)
        self.assertEqual(len(feed['notices']),1);self.assertEqual(historical.to_dict(),before)
        for private in ('gemini','analysis','relevant','relevance_reason','score','keywords'):
            self.assertNotIn(private,feed['notices'][0])

    def test_hash_and_versions_are_validated_as_one_pair(self):
        feed=build_feed([notice()],generated_at=STAMP);meta=dict(schema_version=3,generated_at=STAMP,notice_count=1)
        validate_pair(feed,meta)
        changed=copy.deepcopy(feed);changed['notices'][0]['content_text']='unverified change'
        with self.assertRaisesRegex(SyncError,'INVALID_FEED'): validate_pair(changed,meta)
        with self.assertRaisesRegex(SyncError,'SNAPSHOT_MISMATCH'): validate_pair(feed,{**meta,'schema_version':2})

    def test_active_runtime_imports_no_provider_or_onnx(self):
        code="import src.main, tools.actions_support, sys; assert 'src.ai.gemini' not in sys.modules; assert 'src.ai.work_queue' not in sys.modules; assert 'onnxruntime' not in sys.modules"
        process=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=20)
        self.assertEqual(process.returncode,0,process.stderr)

    def test_archived_provider_default_transport_is_disabled_even_with_a_key(self):
        from src.ai.gemini import GeminiClient,GeminiError,notice_payload
        with patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('retired provider')) as http:
            client=GeminiClient(api_key='synthetic-key',model='synthetic-model')
            with self.assertRaisesRegex(GeminiError,'PROVIDER_RETIRED'): client.generate(notice_payload(notice()))
            http.assert_not_called()

    def test_v2_judgment_cannot_be_reused_as_local_work_judgment(self):
        old=dict(notice_id='n',title='배터리 제조업체 모집',summary='',category='IP',participation_type='수행기관',
                 keywords=['특허'],relevance_reason='OLD GEMINI ELIGIBLE')
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as root:
            result=LocalNoticeAnalysis(Path(root)/'cache',encoder_factory=Encoder,model_version='test').analyze_a([old])['n']
        self.assertEqual(result['status'],'EXCLUDE')
        self.assertNotIn('OLD GEMINI',result['reason'])

    def test_no_company_data_can_enter_public_projection(self):
        historical=notice(gemini=GeminiResult(status='SUCCESS',reason='PRIVATE_COMPANY_SENTINEL'))
        feed=build_feed([historical],generated_at=STAMP)
        self.assertNotIn('PRIVATE_COMPANY_SENTINEL',json.dumps(feed))
