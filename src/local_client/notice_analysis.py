"""Independent local public-work A and private technical B; never network or SQL.

A accepts public mappings only. B receives immutable performance snapshots.
No B result or performance revision is an input to A.
"""
import hashlib
import json
import math
import re
import threading
from pathlib import Path
from .local_model import LocalEncoder, model_directory
from .work_profiles import VERSION, WORK, UNRELATED, PHRASES
from src.core.public_text import public_hash
from src.core.storage import _atomic_json

TECH_VERSION = 'local-technical-v1'
_MODEL_LOCK = threading.Lock()
PUBLIC_FIELDS = ('notice_id','institution','title','summary','content_text','work_scope',
                 'recruitment_type','participation_requirements','apply_start','apply_end')

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def public_only(notice):
    return {k:notice.get(k,'') for k in PUBLIC_FIELDS}

def work_evidence(notice):
    text='\n'.join(str(notice.get(k) or '') for k in PUBLIC_FIELDS if k not in ('notice_id','institution'))
    phrases=[p for p in PHRASES if p.casefold() in text.casefold()]
    if re.search(r'(?<![A-Za-z])IP(?![A-Za-z])',text,re.I) and not phrases: phrases=['IP 전문 업무']
    # Embed actual duty expressions, not product-heavy full titles.
    duties=' / '.join(phrases) or '수행 업무가 명확하게 제공되지 않음'
    provider=bool(re.search(r'수행기관|전문기관|컨설팅.*(?:업체|기관)|용역|위탁',text))
    beneficiary=bool(re.search(r'(?:수혜|지원대상)\s*기업|(?:참여|지원)\s*기업\s*모집|교육생\s*모집|제조업체\s*모집',text))
    manufacturer=bool(re.search(r'제조업체\s*모집|제조업(?:체)?(?:만|에\s*한)|(?:제조업|공장)\s*(?:등록|보유).*필수',text))
    professional=bool(re.search(r'특허법인|변리사|지식재산\s*전문기관',text))
    excluded=bool(re.search(r'(?:특허법인|변리사)\s*(?:은|는)?\s*(?:(?:참가|참여|입찰|신청)\s*)?(?:불가|금지|제외)',text))
    allowed=bool(re.search(r'(?:특허법인|변리사)\s*(?:도|의)?\s*(?:참가|참여|입찰|신청)\s*가능',text))
    negated_exclusion=bool(re.search(r'(?:특허법인|변리사).{0,12}(?:불가|금지|제외)\s*(?:하지|아님|아니)',text))
    mixed_qualification=excluded and (allowed or negated_exclusion)
    if manufacturer and (allowed or re.search(r'특허법인\s*(?:또는|및)|(?:또는|및)\s*특허법인',str(notice.get('title') or ''))):
        manufacturer=False
    unrelated=bool(re.search(r'교육생\s*모집|취업\s*캠프|청소\s*용역|경비\s*용역|급식\s*계약|사무용품\s*구매',text))
    substantive=[p for p in phrases if p not in {'지식재산','지식재산권','IP 전문 업무','권리화','특허출원','특허 출원'}]
    title=str(notice.get('title') or '')
    duty_context=any(p.casefold() in title.casefold() for p in substantive)
    duty_context=duty_context or bool(phrases and re.search(r'컨설팅|권리화.*(?:용역|대행)|특허\s*출원.*(?:용역|대행)',title))
    duty_context=duty_context or bool(re.search(r'(?:수행\s*업무|용역\s*내용|과업\s*내용).{0,120}(?:특허.{0,8}분석|선행기술조사|기술이전\s*컨설팅)',text))
    if re.search(r'선정\s*결과|평가\s*결과|낙찰\s*결과',title): duty_context=False
    if mixed_qualification: duty_context=False
    return dict(duties=duties,phrases=phrases,provider=provider,beneficiary=beneficiary,
                manufacturer=manufacturer,professional=professional,unrelated=unrelated,duty_context=duty_context,
                explicit_exclusion=excluded and not (allowed or negated_exclusion),mixed_qualification=mixed_qualification)

def adapt_notice(notice):
    """Compatibility fields for unchanged matcher; never copy old AI into A."""
    if 'prefilter_status' not in notice: return dict(notice)
    evidence=work_evidence(notice)
    return {**notice,'summary':notice.get('summary',''),'category':evidence['phrases'][0] if evidence['phrases'] else '미분류',
            'participation_type':'수행기관' if evidence['provider'] else '원문 확인 필요',
            'keywords':evidence['phrases'], 'relevance_reason':'사전 필터 통과 · 로컬 업무 분석 필요'}

def technical_text(notice):
    text=' '.join(str(notice.get(k) or '') for k in ('title','summary','content_text','technical_field'))
    for phrase in sorted((*PHRASES,*WORK),key=len,reverse=True): text=re.sub(re.escape(phrase),' ',text,flags=re.I)
    text=re.sub(r'특허|분석|조사|컨설팅|수행기관|용역|모집|공고|전략|연구|지원|사업|및|기획',' ',text)
    return ' '.join(text.split())[:5000]

def performance_input(record):
    return dict(performance_id=record.performance_id,project_name=record.project_name,
                technical_field=record.technical_field,technical_fields=list(getattr(record,'technical_fields',())),
                description=record.description,keywords=list(record.keywords),work_type=record.work_type)

class LocalNoticeAnalysis:
    def __init__(self, cache_path, *, encoder_factory=LocalEncoder, model_version=None):
        self.path=Path(cache_path)
        self.encoder_factory=encoder_factory
        self.model_version=model_version or json.loads((model_directory()/'manifest.json').read_text(encoding='utf-8'))['model_version']
        self.policy=VERSION+':'+digest([WORK,UNRELATED,PHRASES])[:16]
        self.tech_policy=TECH_VERSION+':'+digest([WORK,PHRASES])[:16]
        self._lock=threading.Lock()

    def _read(self,kind):
        try:
            value=json.loads(Path(str(self.path)+'.'+kind+'.json').read_text(encoding='utf-8'))
            return value if isinstance(value,dict) else {}
        except (OSError,ValueError): return {}

    def _cached(self,kind,key):
        with self._lock: return self._read(kind).get(key)

    def _save(self,kind,key,value):
        with self._lock:
            data=self._read(kind);data[key]=value
            _atomic_json(Path(str(self.path)+'.'+kind+'.json'),data)

    def a_key(self,notice):
        return digest([notice['notice_id'],public_hash(public_only(notice)),self.policy,self.model_version])

    def analyze_a(self,notices,*,cancel=None):
        results={}; pending=[]
        for raw in notices:
            notice=public_only(raw);key=self.a_key(notice);cached=self._cached('work',key)
            if (isinstance(cached,dict) and cached.get('status') in ('HIGH','REVIEW','EXCLUDE')
                    and cached.get('model_version')==self.model_version and cached.get('policy_version')==self.policy
                    and cached.get('analysis_state')=='SUCCESS' and isinstance(cached.get('reason'),str)
                    and cached.get('qualification') in ('EVIDENCE','CHECK_REQUIRED','EXPLICIT_EXCLUSION')
                    and type(cached.get('score')) in (int,float) and math.isfinite(cached['score']) and -1.001<=cached['score']<=1.001):
                results[notice['notice_id']]=cached
            else: pending.append((notice,key,work_evidence(notice)))
        if not pending: return results
        try:
            with _MODEL_LOCK,self.encoder_factory() as encoder:
                vectors=encoder.encode([*WORK,*UNRELATED,*[e['duties'] for _,_,e in pending]])
                if cancel and cancel.is_set(): return results
                for i,(notice,key,e) in enumerate(pending):
                    vector=vectors[len(WORK)+len(UNRELATED)+i]
                    positive=max(float(vector @ v) for v in vectors[:len(WORK)])
                    negative=max(float(vector @ v) for v in vectors[len(WORK):len(WORK)+len(UNRELATED)])
                    status='REVIEW'
                    if e['manufacturer'] or e['explicit_exclusion'] or (e['unrelated'] and not e['phrases']): status='EXCLUDE'
                    elif (e['phrases'] and e['duty_context']
                          and not e['beneficiary'] and not e['manufacturer'] and positive>negative): status='HIGH'
                    qualification='EXPLICIT_EXCLUSION' if e['manufacturer'] or e['explicit_exclusion'] else 'EVIDENCE' if e['professional'] and not e['beneficiary'] and not e['mixed_qualification'] else 'CHECK_REQUIRED'
                    result=dict(status=status,qualification=qualification,score=round(positive,6),
                                reason=e['duties'],model_version=self.model_version,policy_version=self.policy,
                                analysis_state='SUCCESS',error_code=None)
                    self._save('work',key,result);results[notice['notice_id']]=result
        except Exception:
            # Do not cache failure as a successful decision. Existing matching
            # policy/hash cache was already reused above, before model loading.
            for notice,key,e in pending:
                results.setdefault(notice['notice_id'],dict(status='REVIEW',qualification='CHECK_REQUIRED',
                    score=None,reason=e['duties'],model_version=self.model_version,policy_version=self.policy,
                    analysis_state='UNAVAILABLE',error_code='LOCAL_MODEL_OR_CACHE_UNAVAILABLE'))
        return results

    def analyze_b(self,notice,performances,*,cancel=None):
        inputs=[performance_input(r) for r in performances]
        revision=digest(inputs)
        key=digest([notice['notice_id'],public_hash(public_only(notice)),self.tech_policy,self.model_version,revision])
        cached=self._cached('technical',key)
        if (isinstance(cached,dict) and cached.get('revision')==revision and cached.get('status')=='SUCCESS'
                and cached.get('policy_version')==self.tech_policy and cached.get('model_version')==self.model_version
                and isinstance(cached.get('rows'),list) and len(cached['rows'])==len(inputs)
                and {r.get('performance_id') for r in cached['rows'] if isinstance(r,dict)}=={r['performance_id'] for r in inputs}
                and all(isinstance(r,dict) and isinstance(r.get('project_name'),str)
                        and type(r.get('technical_similarity')) in (int,float) and math.isfinite(r['technical_similarity'])
                        and -1.001<=r['technical_similarity']<=1.001 for r in cached['rows'])): return cached
        if not inputs: return dict(status='SUCCESS',revision=revision,rows=[])
        public=technical_text(notice)
        texts=[]
        for row in inputs:
            texts.append(technical_text(dict(title=row['project_name'],summary=' '.join([row['technical_field'],*row['technical_fields'],*row['keywords']]),content_text=row['description'])))
        if not public.strip(): return dict(status='INSUFFICIENT_TECHNOLOGY',revision=revision,rows=[])
        try:
            with _MODEL_LOCK,self.encoder_factory() as encoder:
                vectors=encoder.encode([public,*texts])
                if cancel and cancel.is_set(): return dict(status='CANCELLED',revision=revision,rows=[])
                rows=[dict(performance_id=row['performance_id'],project_name=row['project_name'],
                           technical_similarity=round(float(vectors[0] @ vectors[i+1]),6)) for i,row in enumerate(inputs)]
            result=dict(status='SUCCESS',revision=revision,rows=rows,model_version=self.model_version,policy_version=self.tech_policy)
            self._save('technical',key,result);return result
        except Exception:
            return dict(status='UNAVAILABLE',revision=revision,rows=[])
