"""Conservative, versioned and reproducible public-notice prefilter. No AI."""
import hashlib
import json
import re
from dataclasses import replace
from pathlib import Path

def strict_json(text):
    def pairs(items):
        value = {}
        for key,item in items:
            if key in value: raise ValueError('DUPLICATE_POLICY_KEY')
            value[key] = item
        return value
    return json.loads(text, object_pairs_hook=pairs)

def notice_payload(notice):
    return {name:getattr(notice,name) for name in
            ('institution','title','category','published_at','apply_start','apply_end','content_text','url')}

POLICY_PATH = Path(__file__).resolve().parents[2]/'config/prefilter_policy.json'


class Prefilter:
    def __init__(self, path=POLICY_PATH):
        self.policy = strict_json(Path(path).read_text(encoding='utf-8'))
        for field in ('positive_phrases','strong_positive_patterns','positive_context','negative_phrases',
                      'negative_context','ambiguous_context','beneficiary_context'):
            values = self.policy[field]
            if not isinstance(values,list) or not values or any(not isinstance(v,str) or not v for v in values):
                raise ValueError('INVALID_PREFILTER_POLICY')
        if type(self.policy['version']) is not int or self.policy['version'] < 1:
            raise ValueError('INVALID_PREFILTER_POLICY')
        if type(self.policy['minimum_body_chars']) is not int or self.policy['minimum_body_chars'] < 1:
            raise ValueError('INVALID_PREFILTER_POLICY')
        digest = hashlib.sha256(json.dumps(self.policy,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:16]
        self.version = f"prefilter-v{self.policy['version']}:{digest}"
        self.patterns = [re.compile(p,re.I) for p in self.policy['strong_positive_patterns']]

    def classify(self, notice):
        text = re.sub(r'\s+',' ',notice.title+' '+notice.content_text+' '+(notice.category or ''))
        has = lambda name:any(p.casefold() in text.casefold() for p in self.policy[name])
        positive = has('positive_phrases') or any(p.search(text) for p in self.patterns)
        negative = has('negative_phrases')
        if positive and (negative or has('beneficiary_context')):
            return 'REVIEW','MIXED_OR_BENEFICIARY'
        if positive:
            return 'CANDIDATE','PUBLIC_RELATED_WORK'
        if (len(notice.content_text.strip()) < self.policy['minimum_body_chars']
                or '[이미지 본문:' in notice.content_text):
            return 'REVIEW','INSUFFICIENT_BODY'
        if negative and has('negative_context'):
            return 'CLEARLY_UNRELATED','EXPLICIT_UNRELATED_SCOPE'
        return 'REVIEW','UNCERTAIN_PROFESSIONAL_SCOPE'

    def evaluate(self, notice, stamp):
        fingerprint = hashlib.sha256(json.dumps(notice_payload(notice),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        state = notice.analysis
        if state.prefilter_policy_version == self.version and state.prefilter_content_hash == fingerprint:
            return notice
        status, reason = self.classify(notice)
        return replace(notice,analysis=replace(state,prefilter_policy_version=self.version,
            prefilter_content_hash=fingerprint,prefilter_status=status,prefilter_reason_code=reason,evaluated_at=stamp))
