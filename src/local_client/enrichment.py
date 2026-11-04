"""Offline, non-generative enrichment. Only four fields are model-writable."""
import json
import re
from copy import deepcopy

from .local_model import LocalEncoder, ModelError, model_directory
from .matcher import DEFAULT_CATEGORY_GROUPS
from .upload import canonical
from .technical_labels import allowed_technical_fields, selection
from .technical_classifier import (PhraseTechnicalClassifier, direct_mentions, technology_eligible,
                                    POLICY_VERSION)

MODEL_FIELDS = frozenset({'project_name', 'technical_field', 'work_type', 'keywords'})
UNKNOWN = ('', None, '미분류')
STOPWORDS = frozenset('사업 업무 수행 지원 위한 대한 관련 통한 기반 적용 개발 연구 분석 조사 기술 내용 주요 프로젝트 과제 용역 관리 작성 결과 보고 진행 및 또는 해당 것을 있는 한다 입니다 the and for with from this that project research study analysis'.split())


def _text(row):
    lines = [line.strip() for line in [row.project_name or '', *row.match_text.splitlines()]
             if line.strip() and line.strip() != (row.client or '').strip()]
    return '\n'.join(dict.fromkeys(lines))[:6000]


def _technology_text(text):
    # Remove existing matcher task names, not an industry keyword dictionary.
    # This separates the research subject from its patent/consulting work type.
    stripped = text
    tasks = {item for group in DEFAULT_CATEGORY_GROUPS for item in group}
    tasks |= {'특허동향조사', '특허 동향 조사', '선행기술조사', '특허 포트폴리오',
              '지식재산 전략', '특허 분석', '특허 동향', '특허', '동향조사'}
    for task in sorted(tasks, key=len, reverse=True):
        stripped = re.sub(re.escape(task), ' ', stripped, flags=re.IGNORECASE)
    stripped = ' '.join(w for w in stripped.split() if canonical(w) not in STOPWORDS)
    return stripped if sum(ch.isalpha() for ch in stripped) >= 4 else text


_WORK_PATTERN = re.compile(
    r'특허.{0,8}?(?:분석|조사|출원|등록|명세서|분쟁|소송)|명세서.{0,8}?작성|'
    r'기술.{0,4}?(?:이전|가치평가|사업화)|침해.{0,4}?분석|무효.{0,4}?조사|선행기술.{0,3}?조사|'
    r'지식재산.{0,4}?전략|'
    r'patent.{0,35}?(?:analysis|prosecution|filing|landscape|litigation)|'
    r'infringement analysis|technology transfer|commercialization', re.IGNORECASE)


def _work_text(text):
    # Extract original service/action spans so an industry noun does not drown
    # out the work type. The model still chooses/abstains among matcher groups.
    spans = list(dict.fromkeys(_WORK_PATTERN.findall(text)))
    return '; '.join(spans) if spans else text


def keyword_candidates(text):
    tokens = re.findall(r'[A-Za-z가-힣0-9][A-Za-z가-힣0-9&+/-]{1,35}', text)
    values = []
    for token in tokens:
        if (canonical(token) in STOPWORDS or not any(ch.isalpha() for ch in token)
                or re.fullmatch(r'[A-Za-z]{1,8}[-_/]?\d[\w/-]*', token)
                or re.fullmatch(r'\d+(?:년|월|일|원|만원|천원|억원)', token)):
            continue
        if len(token) > 3 and token[-1:] in ('을', '를', '의'):
            token = token[:-1]
        if token not in values:
            values.append(token)
    return values[:32]


def can_infer(row, field_name, force=False):
    if field_name not in MODEL_FIELDS:
        return False
    source = row.field_sources.get(field_name)
    value = getattr(row, field_name)
    if source == 'user':
        return False
    if source not in (None, 'unknown', 'local_model') and value not in (None, '', ()):
        return False
    if field_name == 'keywords':
        return not value or (force and source == 'local_model')
    return value in UNKNOWN or (force and source == 'local_model')


def set_user_value(row, field_name, value):
    if field_name not in ('technical_field', 'work_type'):
        raise ValueError('INVALID_USER_FIELD')
    value = value.strip()
    if field_name == 'technical_field':
        tags = selection(value)
        row.technical_tags = []  # Detailed source terms belong to evidence/keywords.
        row.technical_fields = [{'name': v, 'source': 'user', 'score': None} for v in tags]
        value = row.technical_fields[0]['name'] if row.technical_fields else '미분류'
        row.ai_evidence.pop(field_name, None)
    setattr(row, field_name, value or '미분류')
    row.field_sources[field_name] = 'user'
    row.user_edits.add(field_name)
    row.field_confidence[field_name] = None  # A user choice is not a probability.
    row.issues = [issue for issue in row.issues if not issue.startswith('로컬 AI '+field_name)]
    row.review_required = bool(row.issues) or any(getattr(row, f) in UNKNOWN for f in ('technical_field', 'work_type'))
    refresh_search(row)


def refresh_search(row):
    parts = [row.project_name or '', row.client or '', row.technical_field, row.work_type,
             row.description, *[v['name'] for v in row.technical_fields],
             *[v['name'] for v in row.technical_tags], *row.keywords, row.match_text]
    row.searchable_text = '\n'.join(dict.fromkeys(str(p) for p in parts if p))


def explicit_technical_tags(row, config, *, force=False):
    """Source mentions outrank embedding ambiguity; aliases live in the taxonomy.

    These are evidence-backed, independent tags, not competing top1 predictions.
    Keep the existing broad categories for matcher compatibility and provenance.
    """
    if not technology_eligible(row, force):
        return
    found = direct_mentions(row.project_name, config) or direct_mentions(row.description, config)
    found = [v for v in found if v['category'] in allowed_technical_fields()]
    if not found:
        return
    row.technical_tags = found[:3]
    row.technical_fields = []
    for tag in found:
        if tag['category'] not in {v['name'] for v in row.technical_fields}:
            row.technical_fields.append({'name': tag['category'], 'source': 'deterministic_mapping', 'score': None})
    row.technical_field = row.technical_fields[0]['name']
    row.field_sources['technical_field'] = 'deterministic_mapping'
    row.field_confidence['technical_field'] = None
    row.ai_evidence['technical_field'] = {'decision': '원문 명시 태그', 'tags': deepcopy(row.technical_tags)}
    row.issues = [s for s in row.issues if not s.startswith('로컬 AI technical_field')]
    row.review_required = bool(row.issues) or row.work_type in UNKNOWN
    refresh_search(row)


class SemanticClassifier:
    def __init__(self, encoder=None):
        self.encoder = encoder or LocalEncoder()
        self.config = json.loads((self.encoder.directory/'taxonomy.json').read_text(encoding='utf-8'))
        self.technical, self.work = self.config['technical'], self.config['work']
        allowed = {value for group in DEFAULT_CATEGORY_GROUPS for value in group}
        if any(name not in allowed for name, _ in self.work):
            raise ModelError('WORK_TAXONOMY_CONTRACT')
        # Preserve the original work-type prototype batch and negative references.
        # The technical phrase classifier has its own expanded prototype bank.
        self.legacy_technical = [v for v in self.technical if v[0] != '소부장']
        self.prototypes = self.encoder.encode([description for _, description in self.legacy_technical+self.work]
                                             + self.config['unknown'][:4] + self.config.get('work_unknown', []))
        self.rank_technical_vectors = None
        self.technology = None

    def rank(self, vector, kind, *, subject=None):
        offset = 0 if kind == 'technical_field' else len(self.legacy_technical)
        labels = self.technical if kind == 'technical_field' else self.work
        if kind == 'technical_field':
            if self.rank_technical_vectors is None:
                self.rank_technical_vectors = self.encoder.encode([v[1] for v in self.technical])
            scores = self.rank_technical_vectors @ vector
        else:
            scores = self.prototypes[offset:offset+len(labels)] @ vector
        ranking = sorted(range(len(labels)), key=lambda i: (-float(scores[i]), labels[i][0]))
        top, second = float(scores[ranking[0]]), float(scores[ranking[1]])
        margin = top-second
        unknown_start = len(self.legacy_technical)+len(self.work)
        unknown_end = unknown_start+len(self.config['unknown']) if kind == 'technical_field' else len(self.prototypes)
        unknown_score = float(max(self.prototypes[unknown_start:unknown_end] @ vector))
        accepted = (top >= self.config['min_cosine'] and (kind == 'technical_field' or margin >= self.config['min_margin'])
                    and top > unknown_score + .012)
        if kind == 'work_type' and subject is not None and not _WORK_PATTERN.search(subject):
            accepted = False  # Do not turn an industry noun into an unmentioned service.
        automatic = accepted and top >= self.config['auto_cosine'] and margin >= self.config['auto_margin']
        ranked = [{'name': labels[i][0], 'score': round(float(scores[i]), 6)} for i in ranking[:5]]
        return {'name': ranked[0]['name'] if accepted else '미분류', 'cosine': round(top, 6),
                'runner_up_cosine': round(second, 6), 'margin': round(margin, 6),
                'unknown_cosine': round(unknown_score, 6), 'accepted': accepted,
                'decision': '자동 적용' if automatic else '확인 권장' if accepted else '확인 필요', 'ranked': ranked}

    def enrich(self, rows, *, progress=None, cancel=None, force=False):
        np = self.encoder.np
        for start in range(0, len(rows), 16):
            if cancel and cancel.is_set():
                raise ModelError('CANCELLED')
            batch = rows[start:start+16]
            texts = [_text(row) for row in batch]
            views = [_technology_text(text) for text in texts]
            vectors = self.encoder.encode(texts+views+[_work_text(text) for text in texts], cancel=cancel)
            technical_indexes = [i for i, r in enumerate(batch) if technology_eligible(r, force)]
            technical_results = {}
            if technical_indexes:
                if self.technology is None:
                    self.technology = PhraseTechnicalClassifier(self.encoder, self.config)
                technical_results = dict(zip(technical_indexes,
                    self.technology.classify_many([batch[i] for i in technical_indexes], cancel=cancel)))
            candidate_lists = [keyword_candidates(text) if can_infer(row, 'keywords', force) else []
                               for row, text in zip(batch, texts)]
            all_candidates = list(dict.fromkeys(c for candidates in candidate_lists for c in candidates))
            candidate_vectors = self.encoder.encode(all_candidates, cancel=cancel)
            candidate_index = {text: i for i, text in enumerate(all_candidates)}
            for index, (row, text) in enumerate(zip(batch, texts)):
                row.ai_model_version = self.encoder.version+' / '+self.config['version']
                if sum(ch.isalpha() for ch in text) < 2:
                    _unknown(row, reason='NO_TEXT')
                    if progress:
                        progress(start+index+1, len(rows))
                    continue
                for name, vector in (('technical_field', vectors[len(batch)+index]), ('work_type', vectors[2*len(batch)+index])):
                    if name == 'technical_field':
                        if index not in technical_results:
                            continue
                        evidence = technical_results[index]
                    elif can_infer(row, name, force):
                        evidence = self.rank(vector, name, subject=text)
                    else:
                        continue
                    setattr(row, name, evidence['name'])
                    row.field_sources[name] = 'local_model' if evidence['accepted'] else 'unknown'
                    row.field_confidence[name] = evidence['cosine']
                    row.ai_evidence[name] = evidence
                    if name == 'technical_field':
                        row.technical_fields = evidence['fields']
                        row.technical_tags = evidence['tags']
                        row.normalization_version = 'performance-normalization-4'
                        if evidence['fields']:
                            row.field_sources[name] = evidence['fields'][0]['source']
                            row.field_confidence[name] = evidence['fields'][0]['score']
                    row.issues = [s for s in row.issues if not s.startswith('로컬 AI '+name)]
                    if evidence['decision'] != '자동 적용':
                        row.issues.append('로컬 AI '+name+' '+evidence['decision'])
                if can_infer(row, 'keywords', force):
                    candidates = candidate_lists[index]
                    ranked = sorted(((candidate, float(candidate_vectors[candidate_index[candidate]] @ vectors[index]))
                                     for candidate in candidates), key=lambda v: (-v[1], v[0]))
                    selected = [candidate for candidate, score in ranked if score >= .74][:8]
                    row.keywords = tuple(selected)
                    row.field_sources['keywords'] = 'local_model' if selected else 'unknown'
                    row.field_confidence['keywords'] = round(min((score for _, score in ranked[:len(selected)]), default=0), 6)
                    row.ai_evidence['keywords'] = [{'text': candidate, 'cosine': round(score, 6)} for candidate, score in ranked[:8]]
                if can_infer(row, 'project_name', force):
                    self._project_title(row, cancel)
                row.review_required = bool(row.issues) or any(getattr(row, name) == '미분류' for name in ('technical_field', 'work_type'))
                refresh_search(row)
                if progress:
                    progress(start+index+1, len(rows))

    def _project_title(self, row, cancel):
        protected = {str(value) for value in (row.management_id, row.client, row.start_date, row.end_date, row.year, row.amount) if value}
        candidates = [value for value in row.raw_source.get('columns', {}).values()
                      if isinstance(value, str) and 5 <= len(value.strip()) <= 90
                      and value not in protected and not value.startswith('=') and sum(c.isalpha() for c in value) >= 4]
        if len(candidates) < 2:
            return
        vectors = self.encoder.encode(['업무 프로젝트의 간결한 과제명 또는 사업 제목']+candidates, cancel=cancel)
        scores = vectors[1:] @ vectors[0]
        ranking = sorted(range(len(candidates)), key=lambda i: -float(scores[i]))
        top, margin = float(scores[ranking[0]]), float(scores[ranking[0]]-scores[ranking[1]])
        row.ai_evidence['project_name'] = {'cosine': top, 'margin': margin, 'extractive': True}
        if top >= .82 and margin >= .035:
            row.project_name = candidates[ranking[0]].strip()
            row.field_sources['project_name'] = 'local_model'
            row.field_confidence['project_name'] = top
            row.issues = [s for s in row.issues if s != 'project_name 매핑 확인 필요']

    def close(self):
        self.encoder.close()


def _unknown(row, *, reason='MODEL_ERROR'):
    for name in ('technical_field', 'work_type'):
        if can_infer(row, name) or (name == 'technical_field' and row.field_sources.get(name) != 'user'
                                   and row.technical_field not in allowed_technical_fields()):
            setattr(row, name, '미분류')
            row.field_sources[name] = 'unknown'
            row.field_confidence[name] = None
            if name == 'technical_field':
                row.technical_fields = []
                row.technical_tags = []
                row.ai_evidence[name] = {'name': '미분류', 'accepted': False, 'reason': reason,
                                         'ranked': [], 'policy_version': POLICY_VERSION}
    row.review_required = True


def enrich_rows(rows, *, progress=None, cancel=None, force=False, encoder_factory=LocalEncoder):
    if cancel and cancel.is_set():
        raise ModelError('CANCELLED')
    try:
        config = json.loads((model_directory()/'taxonomy.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        config = {}
    for row in rows:
        explicit_technical_tags(row, config, force=force)
    needed = [row for row in rows if technology_eligible(row, force) or any(can_infer(row, name, force) for name in MODEL_FIELDS)]
    if not needed:
        return None
    if progress:
        progress(0, len(needed))
    if not any(sum(ch.isalpha() for ch in _text(row)) >= 2 for row in needed):
        for row in needed:
            _unknown(row, reason='NO_TEXT')
        return None
    classifier = encoder = None
    try:
        encoder = encoder_factory()
        classifier = SemanticClassifier(encoder)
        working = deepcopy(needed)
        classifier.enrich(working, progress=progress, cancel=cancel, force=force)
        for original, enriched in zip(needed, working):
            for name in MODEL_FIELDS:
                if can_infer(original, name, force) or (name == 'technical_field' and technology_eligible(original, force)):
                    setattr(original, name, getattr(enriched, name))
            for name in ('field_sources', 'field_confidence', 'ai_model_version', 'normalization_version',
                         'technical_fields', 'technical_tags', 'ai_evidence', 'issues', 'review_required', 'searchable_text'):
                setattr(original, name, getattr(enriched, name))
        return None
    except ModelError as error:
        if str(error) == 'CANCELLED':
            raise
        for row in needed:
            _unknown(row)
        return '로컬 분석 모델을 사용할 수 없어 기본 분류로 저장했습니다.'
    except Exception:
        for row in needed:
            _unknown(row)
        return '로컬 분석 모델을 사용할 수 없어 기본 분류로 저장했습니다.'
    finally:
        if classifier:
            classifier.close()
        elif encoder:
            encoder.close()


def prepare_file(path, database_path, *, progress=None, cancel=None):
    from .upload import preview_upload
    from .upload_store import restore_saved_enrichment
    preview = preview_upload(path)
    try:
        restore_saved_enrichment(preview, database_path)
    except Exception:
        preview.warnings.append('기존 실적 분석 이력을 읽지 못했습니다. 저장 시 DB를 다시 확인합니다.')
    _analyze_preview(preview, progress=progress, cancel=cancel)
    return preview


def prepare_existing(database_path, *, progress=None, cancel=None, force=False):
    from .upload import UploadError
    from .upload_store import load_enrichment_preview
    try:
        preview = load_enrichment_preview(database_path)
    except Exception:
        raise UploadError('DATABASE_READ_FAILED') from None
    if not preview.rows:
        raise UploadError('NO_PERFORMANCE_RECORDS')
    _analyze_preview(preview, progress=progress, cancel=cancel, force=force)
    return preview


def _analyze_preview(preview, **kwargs):
    protected = ('management_id', 'client', 'start_date', 'end_date', 'year', 'amount', 'raw_source')
    original = [{name: deepcopy(getattr(row, name)) for name in protected} for row in preview.rows]
    explicit = [{name: deepcopy(getattr(row, name)) for name in MODEL_FIELDS
                 if row.field_sources.get(name) not in (None, 'unknown', 'local_model', 'deterministic_mapping')
                 and not (name == 'technical_field' and row.field_sources.get(name) != 'user' and getattr(row, name) not in allowed_technical_fields())
                 and not (name == 'technical_field' and getattr(row, name) in UNKNOWN and row.field_sources.get(name) != 'user')}
                for row in preview.rows]
    try:
        warning = enrich_rows(preview.rows, **kwargs)
        if warning:
            preview.warnings.append(warning)
    except ModelError as error:
        if str(error) != 'CANCELLED':
            raise
        preview.warnings.append('로컬 분석을 취소했습니다. 기본 분류 미리보기만 표시합니다.')
    changed = sum(getattr(row, name) != source[name] for row, source in zip(preview.rows, original) for name in protected)
    explicit_changed = sum(getattr(row, name) != value for row, source in zip(preview.rows, explicit) for name, value in source.items())
    preview.analysis_stats.update(protected_field_changes=changed, explicit_field_changes=explicit_changed)
    if changed or explicit_changed:
        for row, source, fixed in zip(preview.rows, original, explicit):
            for name, value in {**source, **fixed}.items():
                setattr(row, name, value)
            row.review_required = True
        preview.warnings.append('로컬 모델 결과 검증에 실패해 원본 값을 유지합니다.')
