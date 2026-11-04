"""A public-only eligibility and B private technical analysis stay independent."""
import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from src.local_client.notice_analysis import LocalNoticeAnalysis, public_only, technical_text, adapt_notice
from src.local_client.performance import Performance
from src.local_client.matcher import match_notice

def row(title='전기자동차 배터리팩 하우징 특허분석 용역',**changes):
    return dict(notice_id='n',title=title,**changes)

class Vector(tuple):
    def __matmul__(self,other): return sum(a*b for a,b in zip(self,other))

class Encoder:
    calls=0
    def __enter__(self): type(self).calls+=1;return self
    def __exit__(self,*args): pass
    def encode(self,texts):
        from src.local_client.work_profiles import WORK,UNRELATED
        return [Vector((0,1)) if text in UNRELATED or '명확하게 제공되지 않음' in text else Vector((1,0)) for text in texts]

def broken(): raise RuntimeError('synthetic local model failure')

class LocalStagesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent);self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'snapshot.json'
        self.service=LocalNoticeAnalysis(self.path,encoder_factory=Encoder,model_version='synthetic-v1')

    def test_work_and_qualification_are_separate(self):
        result=self.service.analyze_a([row()])['n']
        self.assertEqual(result['status'],'HIGH')
        self.assertEqual(result['qualification'],'CHECK_REQUIRED')
        self.assertEqual(result['reason'],'특허분석')

    def test_public_only_no_sql_no_network_and_company_fields_ignored(self):
        original=row()
        with patch('sqlite3.connect',side_effect=AssertionError('A must not open DB')),patch('socket.create_connection',side_effect=AssertionError('offline')):
            first=self.service.analyze_a([original])['n']
            for count in (0,100):
                changed={**original,'performances':[{'project_name':'배터리'}]*count,'database_path':'missing.db','client':'synthetic'}
                self.assertEqual(self.service.analyze_a([changed])['n'],first)
                self.assertEqual(self.service.a_key(changed),self.service.a_key(original))

    def test_manufacturer_and_trainees_never_promoted_by_technology(self):
        for title in ('전기자동차 배터리팩 하우징 제조업체 모집','일반 인재양성 교육생 모집'):
            self.assertEqual(self.service.analyze_a([row(title)])['n']['status'],'EXCLUDE')
        result=self.service.analyze_a([row('배터리 제조업체 모집 특허분석 지원')])['n']
        self.assertNotEqual(result['status'],'HIGH')

    def test_mixed_training_consulting_and_beneficiaries(self):
        mixed=self.service.analyze_a([row('특허 전문인력 양성 및 기업 특허 컨설팅 수행기관 모집')])['n']
        self.assertNotEqual(mixed['status'],'EXCLUDE')
        beneficiary=self.service.analyze_a([row('중소기업 특허 지원 참여기업 모집')])['n']
        self.assertEqual(beneficiary['status'],'REVIEW')

    def test_explicit_qualification_is_evidence_not_probability(self):
        result=self.service.analyze_a([row(content_text='참가 자격: 특허법인 또는 변리사')])['n']
        self.assertEqual(result['qualification'],'EVIDENCE')

    def test_explicit_exclusion_and_conflicting_qualification_need_separate_rules(self):
        result=self.service.analyze_a([row(content_text='참가 자격: 특허법인 참여 불가')])['n']
        self.assertEqual((result['status'],result['qualification']),('EXCLUDE','EXPLICIT_EXCLUSION'))
        mixed=self.service.analyze_a([row(content_text='변리사 참여 불가. 특허법인 참여 가능.')])['n']
        self.assertEqual((mixed['status'],mixed['qualification']),('REVIEW','CHECK_REQUIRED'))
        also=self.service.analyze_a([row('특허법인 또는 제조업체 모집',content_text='특허법인 참여 가능.')])['n']
        self.assertNotEqual(also['status'],'EXCLUDE')
        negated=self.service.analyze_a([row(content_text='특허법인은 제외하지 않음')])['n']
        self.assertEqual((negated['status'],negated['qualification']),('REVIEW','CHECK_REQUIRED'))

    def test_unclear_duties_remain_review(self):
        self.assertEqual(self.service.analyze_a([row('전문 용역 수행기관 모집')])['n']['status'],'REVIEW')
        for title,body in (('IP 마이스터 창의인재양성 교육','지식재산 전문기관 지원 프로그램'),
                           ('지식재산대전 행사 운영 용역','기술거래 활성화를 위한 행사 개최'),
                           ('BIO-Europe 참가지원 사업 공고','기술거래 및 해외 진출을 지원합니다.'),
                           ('인공지능 기술사업화 지원사업 최종 선정 결과 안내','기술사업화 전문기관 용역')):
            self.assertEqual(self.service.analyze_a([row(title,content_text=body)])['n']['status'],'REVIEW')

    def test_cache_hit_precedes_model_load_and_failure_is_not_success(self):
        first=self.service.analyze_a([row()])
        failed=LocalNoticeAnalysis(self.path,encoder_factory=broken,model_version='synthetic-v1')
        self.assertEqual(failed.analyze_a([row()]),first)
        result=failed.analyze_a([row('변경된 특허분석 용역')])['n']
        self.assertEqual(result['status'],'REVIEW');self.assertEqual(result['analysis_state'],'UNAVAILABLE')
        self.assertIsNone(result['score'])

    def test_hash_policy_and_model_invalidate_only_a(self):
        first=self.service.a_key(row())
        self.assertNotEqual(first,self.service.a_key(row(content_text='공개 자격 변경')))
        self.service.policy='work-v2';self.assertNotEqual(first,self.service.a_key(row()))
        self.service.policy='work-v1';self.service.model_version='model-v2'
        self.assertNotEqual(first,self.service.a_key(row()))

    def test_b_revision_tracks_add_edit_delete_without_touching_a(self):
        a=self.service.analyze_a([row()]);before=Path(str(self.path)+'.work.json').read_bytes()
        record=Performance(performance_id='p',project_name='배터리 모듈',technical_field='전기전자',work_type='특허분석')
        first=self.service.analyze_b(row(),[record])
        edited=self.service.analyze_b(row(),[replace(record,project_name='반도체 제조기술',technical_field='반도체')])
        added=self.service.analyze_b(row(),[record,replace(record,performance_id='q')])
        deleted=self.service.analyze_b(row(),[])
        self.assertNotEqual(first['revision'],edited['revision']);self.assertEqual(len(added['rows']),2)
        self.assertEqual(deleted['rows'],[])
        self.assertEqual(Path(str(self.path)+'.work.json').read_bytes(),before)
        self.assertEqual(self.service.analyze_a([row()]),a)

    def test_client_and_management_id_not_semantic_inputs(self):
        a=Performance(performance_id='001',project_name='배터리 모듈',client='고객A')
        b=replace(a,client='다른 고객')
        self.assertEqual(self.service.analyze_b(row(),[a]),self.service.analyze_b(row(),[b]))
        self.assertNotIn('특허분석',technical_text(row()))
        self.assertNotIn('특허조사',technical_text(row('식품 포장재 특허조사')))

    def test_b_failure_does_not_mutate_a_or_matcher(self):
        self.service.analyze_a([row()]);before=Path(str(self.path)+'.work.json').read_bytes()
        notice=adapt_notice({**row(),'prefilter_status':'CANDIDATE'})
        records=[Performance(performance_id='p',project_name='배터리 하우징 특허분석',technical_field='배터리',work_type='특허분석')]
        expected=match_notice(notice,records,reference_year=2026)
        failed=LocalNoticeAnalysis(self.path,encoder_factory=broken,model_version='synthetic-v1')
        self.assertEqual(failed.analyze_b(row(),records)['status'],'UNAVAILABLE')
        self.assertEqual(match_notice(notice,records,reference_year=2026),expected)
        self.assertEqual(Path(str(self.path)+'.work.json').read_bytes(),before)

class RealOfflineModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try: import onnxruntime, tokenizers
        except ImportError: raise unittest.SkipTest('optional installed desktop ONNX runtime required')

    def test_real_onnx_work_and_technology_examples_without_network(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder,patch('socket.create_connection',side_effect=AssertionError('offline')):
            service=LocalNoticeAnalysis(Path(folder)/'cache')
            titles=['전기자동차 배터리팩 하우징 특허분석 용역','반도체 특허동향 분석','의료기기 기술이전 컨설팅',
                    '배터리 제조업체 모집','일반 인재양성 교육생 모집','전문 용역 수행기관 모집']
            results=service.analyze_a([dict(row(t),notice_id=str(i)) for i,t in enumerate(titles)])
            self.assertEqual([results[str(i)]['status'] for i in range(6)],['HIGH','HIGH','HIGH','EXCLUDE','EXCLUDE','REVIEW'])
            records=[Performance(performance_id='battery',project_name='전기차 이차전지 배터리 모듈 기술조사'),
                     Performance(performance_id='food',project_name='식품 포장재 특허분석'),
                     Performance(performance_id='semi',project_name='반도체 제조 공정 기술분석'),
                     Performance(performance_id='medical',project_name='의료기기 기술이전')]
            for title,expected in ((titles[0],'battery'),('반도체 제조 공정 특허분석','semi'),('의료기기 기술이전 컨설팅','medical')):
                result=service.analyze_b(row(title),records)
                self.assertEqual(result['status'],'SUCCESS')
                self.assertEqual(max(result['rows'],key=lambda r:r['technical_similarity'])['performance_id'],expected)
