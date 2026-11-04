"""Evidence gates for public professional-work opportunities, independent of AI/B.

Every quoted span comes from public input. Similarity is deliberately not an
argument to this decision. Do not reuse these rules to change legacy matching.
"""
import re

VERSION = 'strict-opportunity-v1'
DUTY = r'(?:특허\s*(?:조사|분석|동향|맵|전략|포트폴리오|출원|컨설팅)|선행\s*기술\s*조사|IP\s*-?\s*R\s*&\s*D|IP\s*전략|지식재산(?:권)?\s*(?:전문\s*)?컨설팅|기술\s*(?:이전|거래)\s*컨설팅|기술\s*가치\s*평가|기술\s*사업화\s*전략|사업화\s*전략|권리화\s*(?:지원|용역))'
RELATED = r'(?:특허기반\s*사업화\s*R&D|표준특허|영업비밀\s*평가|발명가.*?컨설팅|IP-IR\s*심화컨설팅|(?:특허법인|변리사)\s*전문\s*협력기관)'
ACTOR = r'(?:수행\s*(?:기관|업체)|협력\s*기관|전문\s*(?:기관|업체|가)|컨설팅\s*(?:기관|업체)|특허법인|변리사)'
RECRUIT = r'(?:모집|선정|공모|등록\s*(?:신청|모집|공고|접수))'
NEGATIVE_TYPES = (
 ('CANCELLED',r'취소\s*공고'),
 ('RESULT_NOTICE',r'(?:선정|평가|낙찰|선발)\s*결과|(?:선정|모집|공모)\s*(?:완료|종료)|추가\s*지원\s*대상\s*안내'),
 ('CONTEST',r'출품작|아이디어\s*(?:공모|경진)|작품\s*공모|경진대회|공모전'),
 ('VARIETY_ADMINISTRATION',r'국유\s*품종\s*보호권.*(?:처분|관리|이용)'),
 ('BENEFICIARY',r'(?:참여|참가|수혜|입주|희망)\s*기업.*모집|수행기업\s*모집|참가\s*지원|참가지원|컨설팅\s*지원사업.*참여기관\s*모집|인증.*신청|보증지원|창업.*모집'),
 ('EDUCATION',r'교육생|연수생|장학금|채용|취업\s*캠프|인재\s*양성|인재양성|연수\s*프로그램|국외연수|의사과학자\s*양성'),
 ('ADMINISTRATION',r'포상|수요조사|현황\s*및\s*만족도\s*조사'),
 ('PROGRAM_EVALUATION',r'(?:지원\s*사업|지원사업).*성과분석'),
 ('EVENT_OPERATIONS',r'(?:행사|시상식|컨퍼런스|포럼).*운영|전시관|한국관|세미나.*(?:모집|안내)|사전등록|웨비나|할인\s*코드|참가신청|초청장|On-Site Meeting'),
 ('NON_PROFESSIONAL_PROCUREMENT',r'청소\s*용역|경비\s*용역|급식|시설.*공사|물품\s*구매|장비\s*(?:구매|납품)|사무용.*구매|제조업체\s*모집|시스템\s*(?:구축|고도화)|AI\s*모델\s*(?:개발|연구)|탄소\s*저감\s*효과\s*산출'),
)

def span(pattern,text):
    match=re.search(pattern,text,re.I)
    return match.group(0) if match else ''

def classify(notice):
    title=str(notice.get('title') or '')
    body='\n'.join(str(notice.get(k) or '') for k in
        ('content_text','work_scope','recruitment_type','participation_requirements'))
    text=title+'\n'+str(notice.get('summary') or '')+'\n'+body
    original='IMAGE_ONLY' if '[이미지 본문:' in body and len(re.sub(r'\[이미지 본문:[^\]]*\]|https?://\S+','',body).strip())<20 else 'TEXT_AVAILABLE' if body.strip() else 'NOT_COLLECTED'
    duty=span(DUTY,text)
    related=span(RELATED,text)
    # A provider term must be linked to an actual recruiting action, not merely
    # mentioned as a former contractor or a service supplied to beneficiaries.
    provider=span(ACTOR+r'[^\n.!?]{0,45}'+RECRUIT,text)
    service=span(r'[^\n.!?]{0,100}(?:용역|입찰|위탁)[^\n.!?]{0,50}',title)
    tender=span(r'나라장터\s*공고|입찰서\s*및\s*제안서\s*제출|입찰\s*공고',body)
    if not provider and (duty or related): provider=service or tender
    negative=next(((code,span(pattern,title)) for code,pattern in NEGATIVE_TYPES if span(pattern,title)),None)
    # Separate, explicit professional recruitment can coexist with education or
    # beneficiary recruitment. Generic 용역/전문기관 mentions cannot override.
    separate=span(DUTY+r'[^\n.!?]{0,65}'+ACTOR+r'[^\n.!?]{0,25}(?:모집|선정|공모)',text)
    explicit=span(r'(?:특허법인|변리사)\s*(?:은|는)?\s*(?:(?:참가|참여|입찰|신청)\s*)?(?:불가|금지|제외)',text)
    allowed=span(r'(?:특허법인|변리사)\s*(?:도|는|은)?\s*(?:참가|참여|입찰|신청)\s*가능',text)
    negated=span(r'(?:특허법인|변리사).{0,12}(?:불가|금지|제외)\s*(?:하지|아님|아니)',text)
    conflict=bool(explicit and (allowed or negated))
    qualification='CHECK_REQUIRED'
    if explicit and not conflict: qualification='EXPLICIT_EXCLUSION'
    elif span(r'(?:참가|신청|입찰)\s*자격[^\n]{0,70}(?:특허법인|변리사|지식재산\s*전문기관)',text) or allowed: qualification='EVIDENCE'
    if conflict: qualification='CHECK_REQUIRED'
    exclusive=span(r'(?:신청자격|모집분야)[^\n]{0,90}회계법인',text)
    status='EXCLUDE';code='NO_PROFESSIONAL_OPPORTUNITY';reason='관련 전문 업무와 수행기관 모집의 동시 근거 없음'
    if qualification=='EXPLICIT_EXCLUSION' or exclusive:
        qualification='EXPLICIT_EXCLUSION';code='QUALIFICATION_EXCLUSION';reason=explicit or exclusive
    elif negative and (negative[0] in ('CANCELLED','RESULT_NOTICE') or not separate):
        code=negative[0];reason=negative[1]+' — 별도 특허법인 전문 업무 모집 근거 없음'
    elif (duty or related) and span(ACTOR+r'[^\n.!?]{0,45}'+RECRUIT,title) and original in ('NOT_COLLECTED','IMAGE_ONLY'):
        # The title itself can explicitly recruit a patent-work partner. This
        # is evidence, not an inference from missing detail. Never HIGH without
        # the original; separately flag unavailable text for re-collection.
        status='REVIEW';code='EXPLICIT_TITLE_RECRUITMENT';reason=(duty or related)+' / '+provider+' — 원문 정보 부족, 세부 역할·자격 확인 필요'
    elif original in ('NOT_COLLECTED','IMAGE_ONLY'):
        status='INSUFFICIENT';code='ORIGINAL_NOT_AVAILABLE';reason='원문 텍스트 부족 — 전문 업무 모집으로 추정하지 않음'
    elif duty and provider:
        status='REVIEW' if conflict or not service and not tender and not span(r'(?:수행|협력)\s*기관',provider) else 'HIGH'
        code='WORK_AND_PROVIDER_CONFIRMED';reason=duty+' / '+provider
    elif related and provider and (service or span(ACTOR,provider) or ('컨설팅' in related and tender)):
        status='REVIEW';code='RELATED_ROLE_NEEDS_CHECK';reason=related+' / '+provider+' — 세부 수행 업무·자격 확인 필요'
    elif ((related or duty) and span(r'나라장터|첨부|문의처',body)) or span(ACTOR+r'.{0,40}'+RECRUIT,title):
        # Missing detail is recorded for re-collection rather than guessed REVIEW.
        status='INSUFFICIENT';code='MISSING_WORK_OR_RECRUITMENT';reason='세부 전문 업무 또는 실제 수행기관 모집 근거 부족'
    return dict(status=status,display=status in ('HIGH','REVIEW'),qualification=qualification,
        recruitment_type=negative[0] if negative and not separate else '전문 수행기관 모집' if provider else '수행기관 모집 미확인',
        actual_work=(duty or related) if status in ('HIGH','REVIEW') else '',
        detected_work_expression=duty or related,provider_evidence=provider,qualification_evidence=explicit or allowed or exclusive,
        reason=reason,reason_code=code,original_availability=original,
        information_status='INSUFFICIENT' if original!='TEXT_AVAILABLE' else 'AVAILABLE',
        needs_recollection=original!='TEXT_AVAILABLE' or status=='INSUFFICIENT')

def is_displayable(result):
    return bool(result and result.get('status') in ('HIGH','REVIEW') and result.get('display') is True
                and result.get('actual_work') and result.get('provider_evidence'))
