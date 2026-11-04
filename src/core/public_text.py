"""Public text minimization shared by publication; no provider dependencies."""
import hashlib
import json
import re

PUBLIC_TEXT_FIELDS = ('title','summary','content_text','work_scope','recruitment_type','participation_requirements')

def mask_contacts(text):
    text = re.sub(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '[이메일 비공개]', text)
    text = re.sub(r'(?<!\d)(?:\+82[- .]?)?0\d{1,2}[- .]\d{3,4}[- .]\d{4}(?!\d)', '[전화번호 비공개]', text)
    text = re.sub(r'(?<!\d)01[016789]\d{7,8}(?!\d)','[전화번호 비공개]',text)
    return re.sub(r'((?:담당자|담당\s*성명)\s*[:：]\s*)[가-힣]{2,4}(?=\s|$|[,(/])',r'\1[담당자 비공개]',text)

def public_hash(row):
    data={k:row.get(k,'') for k in PUBLIC_TEXT_FIELDS}
    data.update({k:row.get(k) for k in ('apply_start','apply_end','institution')})
    return hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
