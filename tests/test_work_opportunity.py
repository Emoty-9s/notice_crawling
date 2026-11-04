"""Actual procurement evidence gates; embeddings cannot promote unrelated work."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.local_client.work_opportunity import classify,is_displayable
from src.local_client.notice_analysis import LocalNoticeAnalysis
from test_local_notice_analysis import Encoder

def notice(title,body=None):
    return dict(notice_id='public',title=title,content_text=title+' 공고' if body is None else body)

class OpportunityTests(unittest.TestCase):
    def test_actual_professional_procurement(self):
        for title in ('특허조사·특허분석 용역','특허동향 조사·특허맵 구축 용역','선행기술조사 용역',
                      'IP-R&D 전략 수행기관 모집','특허전략 수립 용역','지식재산 컨설팅 수행기관 모집',
                      '기술이전 컨설팅 용역','기술거래 컨설팅 용역','기술사업화 전략 수행기관 모집',
                      '기술가치평가 전문 용역'):
            with self.subTest(title=title):
                n=notice(title);r=classify(n)
                self.assertTrue(is_displayable(r))
                self.assertIn(r['actual_work'],title)
                self.assertIn(r['provider_evidence'],title)

    def test_default_excluded_types_even_with_ip_words(self):
        for title in ('지식재산 출품작 공모전','특허 아이디어 작품 공모','발명품 경진대회',
                      '중소기업 특허지원사업 참여기업 모집','IP 인재양성 교육생 모집','특허 장학금',
                      '지식재산 전문기관 채용','IP 전시회 참가기업 모집','특허전략 수행기관 선정 결과',
                      '지식재산 행사 안내','국유품종보호권(임시보호권) 처분 공고',
                      'IP 사업관리시스템 구축 용역','전기차 제조업체 모집','특허 지원 사무용 책상 구매',
                      '민관협력 IP전략지원 사업 수혜기업 현황 및 만족도 조사 용역',
                      '[취소공고] 특허분석 용역'):
            with self.subTest(title=title):
                self.assertEqual(classify(notice(title))['status'],'EXCLUDE')

    def test_provider_mentions_do_not_rescue_beneficiary_recruitment(self):
        r=classify(notice('특허지원사업 참여기업 모집','지식재산 전문기관이 특허분석 용역을 수행합니다. 수혜기업 모집.'))
        self.assertFalse(is_displayable(r))
        self.assertEqual(r['recruitment_type'],'BENEFICIARY')
        self.assertEqual(r['actual_work'],'')

    def test_pool_mention_and_completed_selection_are_not_active_recruitment(self):
        for title in ('IP-R&D 협력기관 풀 안내','특허분석 수행기관 선정 완료 안내'):
            self.assertFalse(is_displayable(classify(notice(title))))

    def test_separate_related_professional_recruitment_preserved(self):
        for title in ('특허 전문인력 양성 및 기업 특허 컨설팅 수행기관 모집',
                      '기술사업화 교육 및 기술이전 컨설팅 수행기관 모집'):
            self.assertTrue(is_displayable(classify(notice(title))))

    def test_review_requires_work_and_recruitment(self):
        r=classify(notice('특허기반 사업화 R&D 지원사업 용역'))
        self.assertEqual(r['status'],'REVIEW');self.assertTrue(is_displayable(r))
        for title in ('전문 용역 수행기관 모집','특허분석 소개','IP 전문기관 안내'):
            self.assertFalse(is_displayable(classify(notice(title))))

    def test_missing_original_separate_and_recollectable(self):
        for body in ('','[이미지 본문: 텍스트 미추출, OCR 미수행] https://example.test/image.png'):
            r=classify(notice('지식재산 전문기관 모집',body))
            self.assertEqual(r['status'],'INSUFFICIENT');self.assertTrue(r['needs_recollection'])
            self.assertFalse(is_displayable(r))

    def test_explicit_title_proof_does_not_require_guessing_missing_body(self):
        r=classify(notice('표준특허 협력기관 후보군(풀) 모집 공고',''))
        self.assertEqual(r['status'],'REVIEW');self.assertTrue(is_displayable(r))
        self.assertEqual(r['information_status'],'INSUFFICIENT')
        self.assertTrue(r['needs_recollection']);self.assertEqual(r['provider_evidence'],'협력기관 후보군(풀) 모집')

    def test_certain_title_exclusion_and_missing_original_both_recorded(self):
        r=classify(notice('지식재산 출품작 공모전',''))
        self.assertEqual(r['status'],'EXCLUDE');self.assertTrue(r['needs_recollection'])
        self.assertEqual(r['original_availability'],'NOT_COLLECTED')

    def test_youth_is_not_cleaning_and_specialized_education_not_lost(self):
        r=classify(notice('2026 YIP(청소년 발명가 프로그램) 교육·컨설팅 용역',
            '용역명: 2026 YIP(청소년 발명가 프로그램) 교육·컨설팅 용역. 나라장터 공고 사항'))
        self.assertEqual(r['status'],'REVIEW');self.assertTrue(is_displayable(r))

    def test_similarity_one_cannot_override_evidence(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            service=LocalNoticeAnalysis(Path(folder)/'cache',encoder_factory=Encoder,model_version='test')
            r=service.analyze_a([notice('지식재산 출품작 공모전')])['public']
            self.assertEqual(r['score'],1.0)
            self.assertEqual(r['status'],'EXCLUDE');self.assertFalse(is_displayable(r))

    def test_company_data_no_effect_and_legacy_adapter_unchanged(self):
        from src.local_client.notice_analysis import adapt_notice
        n=notice('전기차 제조업체 모집')
        with patch('sqlite3.connect',side_effect=AssertionError('No company DB')):
            a=classify(n)
            self.assertEqual(a,classify({**n,'performances':[{'project_name':'전기차'}]*100}))
        adapted=adapt_notice({**notice('특허분석 용역'),'prefilter_status':'CANDIDATE'})
        self.assertEqual(adapted['category'],'특허분석')
        self.assertEqual(adapted['participation_type'],'수행기관')

    def test_pending_or_legacy_review_cannot_enter_default_list(self):
        self.assertFalse(is_displayable(None))
        self.assertFalse(is_displayable(dict(status='REVIEW',score=.999)))
        self.assertFalse(is_displayable(dict(status='HIGH',display=True,actual_work='특허분석')))

    def test_qualification_is_not_invented_from_ip(self):
        r=classify(notice('특허분석 용역'))
        self.assertEqual(r['qualification'],'CHECK_REQUIRED')
        self.assertEqual(r['qualification_evidence'],'')
        r=classify(notice('국가연구개발비 위탁정산기관 선정 공고','신청자격 한국공인회계사회에 등록된 회계법인'))
        self.assertEqual(r['qualification'],'EXPLICIT_EXCLUSION')
