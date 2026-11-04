"""Offline title/phrase multilabel classification; no generated facts or network."""
import re
from .technical_labels import allowed_technical_fields


POLICY_VERSION = 'closed-taxonomy-multilabel-1'
TECH_UNKNOWN = ('', None, '미분류')
GENERIC = frozenset('기반 활용 이용 통한 위한 관련 관한 대한 및 또는 적용 시스템 기술 개발 연구 분석 조사 사업 과제 프로젝트 용역 업무 수행 지원 전략 수립 방법 장치 구조 가공 보고서 결과 보고 동향 선행 특허 산업 범용 특수 정밀 IP R&D IP-R&D the and for with based using system technology development research study analysis of in to a an'.lower().split())
WORK = re.compile(r'특허\s*(?:동향\s*)?(?:조사|분석|출원|등록)|선행\s*기술\s*조사|IP[-\s]?R[&＆]D|특허맵|특허|patent\s*(?:landscape|analysis|research)?', re.I)
TOKEN = re.compile(r'[A-Za-z가-힣][A-Za-z가-힣0-9+/-]*')


def clean_subject(text):
    return ' '.join(w for w in WORK.sub(' ', text or '').split() if w.lower() not in GENERIC)


def extract_phrases(text, *, limit=18):
    """Source-only noun/phrase candidates, independent of a complete keyword list."""
    cleaned = clean_subject(text)
    tokens = []
    for match in TOKEN.finditer(cleaned):
        word = re.sub(r'(?:용|에서|으로|위한|관련|기반)$', '', match.group())
        if len(word) < 2 or word.lower() in GENERIC or re.fullmatch(r'[A-Za-z]{1,8}[-_/]?\d[\w/-]*', word):
            continue
        tokens.append(word)
    result = list(dict.fromkeys(tokens))
    # Spaces in English/Korean noun phrases are retained; each single noun also
    # gets its own vector, so two fields do not compete for a single top1 slot.
    for size in (2, 3):
        result += [' '.join(tokens[i:i+size]) for i in range(len(tokens)-size+1)]
    return list(dict.fromkeys(result))[:limit]


def direct_mentions(text, config):
    found = []
    for tag in config.get('technical_tags', []):
        for alias in tag['aliases']:
            pattern = re.escape(alias).replace(r'\ ', r'\s*')
            if re.search(r'[a-zA-Z]', alias):
                pattern = r'(?<![a-zA-Z0-9])'+pattern+r'(?![a-zA-Z0-9])'
            matches = list(re.finditer(pattern, text or '', re.I))
            if matches:
                match = matches[0]
                found.append({'name': tag['name'], 'category': tag['category'], 'source': 'deterministic_mapping',
                              'score': None, 'evidence': match.group(), 'position': match.start()})
                break
    return sorted(found, key=lambda v: v['position'])


def technology_eligible(row, force=False):
    source = row.field_sources.get('technical_field')
    if source == 'user':
        return False
    if row.technical_field not in TECH_UNKNOWN and row.technical_field not in allowed_technical_fields():
        return True  # Preserve the original cell as evidence, not a new label.
    if source not in (None, 'unknown', 'local_model', 'deterministic_mapping'):
        # A legacy/imported "미분류" is missing information, not an explicit
        # technical fact. Only a user's deliberate unknown is protected above.
        return row.technical_field in TECH_UNKNOWN
    # Upgrade the older tag-as-field representation as well as old AI abstentions.
    old_policy = row.ai_evidence.get('technical_field', {}).get('policy_version') != POLICY_VERSION
    return row.technical_field in TECH_UNKNOWN or force or (source == 'deterministic_mapping' and old_policy)


class PhraseTechnicalClassifier:
    def __init__(self, encoder, config):
        self.encoder, self.config = encoder, config
        self.policy = config.get('technical_policy', {})
        self.labels = [v[0] for v in config['technical']]
        self.examples, self.owners = [], []
        for index, (label, description) in enumerate(config['technical']):
            # A handful of representative examples, not an exhaustive manual
            # industry-keyword mapping. Unseen source phrases use embeddings.
            examples = list(dict.fromkeys([description, description.rsplit('. ', 1)[-1],
                                           *config.get('technical_examples', {}).get(label, [])]))
            self.examples.extend(examples)
            self.owners.extend([index]*len(examples))
        self.vectors = encoder.encode(self.examples+config['unknown'])
        self.nontech = self.vectors[len(self.examples):]
        self.vectors = self.vectors[:len(self.examples)]

    def classify_many(self, rows, *, cancel=None):
        np = self.encoder.np
        views = []
        for row in rows:
            title = clean_subject(row.project_name)
            description = clean_subject(row.description)[:1600]
            raw = clean_subject(row.match_text)[:1600]
            per_row = [(title, 'title', 1.0)] if title else []
            per_row += [(p, 'title_phrase', 1.0) for p in extract_phrases(row.project_name)]
            per_row += [(p, 'description_phrase', .92) for p in extract_phrases(description, limit=10)]
            if not title and not description:
                per_row += [(p, 'raw_phrase', .85) for p in extract_phrases(raw, limit=10)]
            # Keep complete long description only when the title lacks a subject.
            if not title and description:
                per_row.insert(0, (description, 'description', .92))
            views.append(list(dict.fromkeys(per_row)))
        texts = list(dict.fromkeys(text for row_views in views for text, _, _ in row_views))
        vectors = self.encoder.encode(texts, cancel=cancel)
        lookup = {text: i for i, text in enumerate(texts)}
        raw_scores = vectors @ self.vectors.T
        scores = np.stack([raw_scores[:, [i for i, owner in enumerate(self.owners) if owner == label]].max(axis=1)
                           for label in range(len(self.labels))], axis=1) if texts else np.empty((0, len(self.labels)))
        unknown = (vectors @ self.nontech.T).max(axis=1) if texts else []
        return [self._aggregate(row, row_views, lookup, scores, unknown) for row, row_views in zip(rows, views)]

    def _aggregate(self, row, views, lookup, scores, unknown):
        strong = self.policy.get('strong_cosine', .84)
        secondary = self.policy.get('secondary_cosine', .86)
        lead = self.policy.get('nontechnical_lead', .025)
        candidates, support, tags = {}, {}, []
        title_mentions = direct_mentions(row.project_name, self.config)
        # A clear title takes precedence over boilerplate in description/raw data.
        mentions = title_mentions or direct_mentions(row.description, self.config)
        for mention in mentions:
            label = mention['category']
            support[label] = {'name': label, 'score': None, 'source': 'deterministic_mapping', 'phrase': mention['evidence'], 'origin': 'title' if title_mentions else 'description'}
            tags.append(mention)
        evidence_phrases = []
        independent = set()
        has_title = any(origin.startswith('title') for _, origin, _ in views)
        for text, origin, weight in views:
            index = lookup[text]
            ranking = sorted(range(len(self.labels)), key=lambda j: (-float(scores[index, j]), j))
            is_title = origin.startswith('title')
            for rank, label_index in enumerate(ranking[:5]):
                score, nontech = float(scores[index, label_index]), float(unknown[index])
                name = self.labels[label_index]
                item = {'name': name, 'score': round(score, 6), 'phrase': text, 'origin': origin,
                        'unknown_cosine': round(nontech, 6), 'weighted_score': round(score*weight, 6), 'source': 'local_model'}
                if name not in candidates or item['weighted_score'] > candidates[name]['weighted_score']:
                    candidates[name] = item
                # Per-phrase top1 is independent of every other phrase's top1.
                # No top1/top2 margin is used to accept/reject a technical field.
                threshold = strong if rank == 0 else max(secondary, .91)
                if origin.endswith('phrase'):
                    threshold = max(threshold, self.policy.get('phrase_cosine', .89))
                # A complete title may support several sufficiently strong labels;
                # an individual short noun votes for its own best category.
                if rank >= 2:
                    threshold = max(threshold, .93)
                accepted = score >= threshold and score >= nontech+lead and rank < (3 if origin == 'title' else 1)
                if name == '소부장':
                    # Orthogonal materials/components/equipment role may accompany
                    # a specialist field even when both score almost identically.
                    accepted = score >= .91 and score >= nontech+lead
                if not is_title:
                    accepted = accepted and score >= (.94 if has_title else .89)
                if accepted:
                    if origin.endswith('phrase') and (rank == 0 or name == '소부장'):
                        independent.add(name)
                    old = support.get(name)
                    if old is None or (old['source'] != 'deterministic_mapping' and item['weighted_score'] > old.get('weighted_score', 0)):
                        support[name] = item
                    if origin.endswith('phrase') and len(text.split()) <= 2:
                        evidence_phrases.append({'name': text, 'category': name, 'score': round(score, 6), 'source': 'local_model', 'origin': origin})
        # Title-supported fields precede description-only evidence regardless of
        # description length. Explicit source evidence is first within that level.
        support = {name: value for name, value in support.items() if name in self.labels}
        if '소부장' in support:
            # Generic component nouns must not manufacture an unrelated specialist
            # domain from a full title's weaker runner-up alone.
            support = {name: value for name, value in support.items() if name == '소부장'
                       or name in independent or value['source'] == 'deterministic_mapping'}
        fields = sorted(support.values(), key=lambda v: (
            0 if v['origin'].startswith('title') else 1,
            0 if v['source'] == 'deterministic_mapping' else 1,
            -v.get('weighted_score', 0)))[:3]
        fields = [v for i, v in enumerate(fields) if i == 0 or v['score'] is None or v['score'] >= secondary]
        names = {v['name'] for v in fields}
        phrase_tags = sorted(evidence_phrases, key=lambda v: (
            0 if v['origin'].startswith('title') else 1, len(v['name'].split()),
            (row.project_name or '').find(v['name']) if v['origin'].startswith('title') else 0, -v['score']))
        # Preserve source phrases absent from the taxonomy, not generated labels.
        for tag in phrase_tags:
            if tag['category'] in names and tag['name'].lower() not in {v['name'].lower() for v in tags}:
                tags.append(tag)
        tags = [v for v in tags if v['category'] in names][:self.policy.get('max_tags', 3)]
        ranked = sorted(candidates.values(), key=lambda v: -v['weighted_score'])[:5]
        top = ranked[0]['score'] if ranked else 0
        runner = ranked[1]['score'] if len(ranked) > 1 else 0
        accepted = bool(fields)
        if accepted:
            reason = None
        elif not views:
            reason = 'NO_TEXT'
        elif top < strong:
            reason = 'LOW_SCORE'
        else:
            reason = 'NO_LABEL_MATCH'  # General/admin text won the contrast test.
        return {'name': fields[0]['name'] if fields else '미분류', 'fields': fields, 'tags': tags,
                'cosine': top, 'runner_up_cosine': runner, 'margin': round(top-runner, 6),
                'accepted': accepted, 'decision': '자동 적용' if accepted else '확인 필요',
                'ranked': ranked, 'reason': reason, 'policy_version': POLICY_VERSION,
                'direct_terms': mentions, 'phrase_candidates': [v[0] for v in views if v[1].endswith('phrase')],
                'phrase_evidence': evidence_phrases}
