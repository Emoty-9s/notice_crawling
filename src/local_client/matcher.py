"""M14 deterministic local-only matching. No network, AI, embeddings or clock."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, fields

from .performance import Performance, PerformanceStore


class MatchInputError(ValueError):
    """Fixed validation diagnostic; no private record contents."""


@dataclass(frozen=True)
class MatchWeights:
    """All scoring weights live here; nonnegative integer points only."""

    technical_field: int = 5
    work_type: int = 5
    keyword: int = 2
    category: int = 3
    title: int = 2
    recent: int = 1

    def __post_init__(self):
        if any(type(getattr(self, field.name)) is not int or getattr(self, field.name) < 0 for field in fields(self)):
            raise MatchInputError('INVALID_MATCH_WEIGHTS')


DEFAULT_WEIGHTS = MatchWeights()
# Explicit editable category relations, not inferred synonyms. Exact normalized
# category/work-type/technical-field/keyword equality also counts without groups.
DEFAULT_CATEGORY_GROUPS = (
    ('IP-R&D', 'IP R&D', '특허분석', '특허동향분석', '특허전략', 'IP전략', 'IP 전략', '특허맵'),
    ('기술이전', '기술사업화', '사업화', '기술가치평가'),
    ('특허출원', '출원', '권리화', '해외출원'),
    ('특허분쟁', '분쟁대응', '침해분석', '무효조사'),
)
TITLE_STOPWORDS = frozenset({
    '공고', '모집', '모집공고', '입찰', '사업', '안내', '지원', '용역', '신청', '선정',
    '기관', '참여', '수행', '협력', '및', '관련', '위한', '대한', '추진', '의', '과제', '계획', '신규',
})
_DASHES = str.maketrans({char: '-' for char in '‐‑‒–—−'})
_TOKEN = re.compile(r'[^\W_]+(?:[-&][^\W_]+)*')


def _normalize(value):
    if not isinstance(value, str) or '\x00' in value:
        raise MatchInputError('INVALID_MATCH_TEXT')
    try:
        value.encode('utf-8')
    except UnicodeError:
        raise MatchInputError('INVALID_MATCH_TEXT') from None
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().translate(_DASHES).split())


def _contains(term, texts):
    # Unicode alphanumeric boundaries: AI does not match chair, 반도체 does not
    # match 반도체장비. A multiword phrase must occur in a single source field.
    if not term:
        return False
    pattern = re.compile(r'(?<![^\W_])' + re.escape(term) + r'(?![^\W_])')
    return any(pattern.search(text) is not None for text in texts)


def _title_terms(text):
    return {word for word in _TOKEN.findall(text)
            if len(word) >= 2 and word not in TITLE_STOPWORDS and not re.fullmatch(r'\d+(?:년|월|일|차)?', word)}


@dataclass(frozen=True)
class ScoreReason:
    rule: str
    points: int
    terms: tuple[str, ...]


@dataclass(frozen=True)
class MatchResult:
    performance_id: str
    score: int
    matched_terms: tuple[str, ...]
    reasons: tuple[ScoreReason, ...]

    def to_dict(self):
        """JSON-ready local result; no saving/uploading or full private record."""
        return {
            'performance_id': self.performance_id, 'score': self.score,
            'matched_terms': list(self.matched_terms),
            'reasons': [{'rule': reason.rule, 'points': reason.points, 'terms': list(reason.terms)}
                        for reason in self.reasons],
        }


def _prepare(notice, reference_year, top_n, weights, recent_years, category_groups):
    if type(reference_year) is not int or not 1 <= reference_year <= 9999:
        raise MatchInputError('INVALID_REFERENCE_YEAR')
    if type(top_n) is not int or top_n < 0:
        raise MatchInputError('INVALID_TOP_N')
    if not isinstance(weights, MatchWeights):
        raise MatchInputError('INVALID_MATCH_WEIGHTS')
    if type(recent_years) is not int or recent_years < 0:
        raise MatchInputError('INVALID_RECENT_YEARS')
    names = ('category', 'participation_type', 'title', 'summary', 'keywords')
    if not isinstance(notice, Mapping) or any(name not in notice for name in names):
        raise MatchInputError('INVALID_MATCH_NOTICE')
    if not isinstance(notice['keywords'], (list, tuple)):
        raise MatchInputError('INVALID_MATCH_KEYWORDS')
    data = {name: _normalize(notice[name]) for name in names if name != 'keywords'}
    data['keywords'] = frozenset(term for value in notice['keywords'] if (term := _normalize(value)))
    if not isinstance(category_groups, (list, tuple)):
        raise MatchInputError('INVALID_CATEGORY_GROUPS')
    groups = []
    for group in category_groups:
        if not isinstance(group, (list, tuple, set, frozenset)):
            raise MatchInputError('INVALID_CATEGORY_GROUPS')
        groups.append(frozenset(term for value in group if (term := _normalize(value))))
    return data, tuple(groups)


def _score(data, record, reference_year, weights, recent_years, groups):
    technical = _normalize(record.technical_field)
    work = _normalize(record.work_type)
    keywords = frozenset(term for value in record.keywords if (term := _normalize(value)))
    project = _normalize(record.project_name)
    description = _normalize(record.description)
    notice_texts = (data['category'], data['participation_type'], data['title'], data['summary'], *data['keywords'])
    record_texts = (technical, work, project, description, *keywords)
    reasons = []

    def add(rule, points, terms):
        if points > 0:
            reasons.append(ScoreReason(rule, points, tuple(sorted(set(terms)))))

    if _contains(technical, notice_texts):
        add('technical_field', weights.technical_field, (technical,))
    if _contains(work, notice_texts):
        add('work_type', weights.work_type, (work,))
    common_keywords = sorted(term for term in data['keywords'] if _contains(term, record_texts))
    if common_keywords:
        add('keyword', weights.keyword * len(common_keywords), common_keywords)

    category = data['category']
    category_values = {technical, work, *keywords} - {''}
    related = {value for value in category_values
               if category and (value == category or any(category in group and value in group for group in groups))}
    if related:
        add('category', weights.category, related | {category})
    title_terms = _title_terms(data['title']) & _title_terms(project)
    if title_terms:
        add('title', weights.title, title_terms)
    if record.year is not None and 0 <= reference_year - record.year < recent_years:
        add('recent', weights.recent, (str(record.year),))

    matched_terms = tuple(sorted({term for reason in reasons if reason.rule != 'recent' for term in reason.terms}))
    return MatchResult(record.performance_id, sum(reason.points for reason in reasons), matched_terms, tuple(reasons))


def match_notice(notice, performances, *, reference_year, top_n=5, weights=DEFAULT_WEIGHTS,
                 recent_years=3, category_groups=DEFAULT_CATEGORY_GROUPS):
    """Score an M12 notice against Performance records without I/O or mutation.

    reference_year is explicit to avoid date-dependent results. Recent means
    this year and the previous recent_years-1 years; future/unknown years get 0.
    Ties sort by exact performance_id ascending. Zero-score records are retained.
    """
    data, groups = _prepare(notice, reference_year, top_n, weights, recent_years, category_groups)
    try:
        iterator = iter(performances)
    except TypeError:
        raise MatchInputError('INVALID_PERFORMANCES') from None
    results, identities = [], set()
    for record in iterator:
        if not isinstance(record, Performance):
            raise MatchInputError('EXPECTED_PERFORMANCE')
        if record.performance_id in identities:
            raise MatchInputError('DUPLICATE_PERFORMANCE_ID')
        identities.add(record.performance_id)
        results.append(_score(data, record, reference_year, weights, recent_years, groups))
    return sorted(results, key=lambda result: (-result.score, result.performance_id))[:top_n]


def match_store(notice, store, *, reference_year, top_n=5, weights=DEFAULT_WEIGHTS,
                recent_years=3, category_groups=DEFAULT_CATEGORY_GROUPS):
    """Local SQLite integration: read all records, including beyond search's 100.

    One SELECT gives one consistent read snapshot. No schema/data/cache writes.
    Database errors propagate; do not turn a broken database into empty matches.
    """
    if not isinstance(store, PerformanceStore):
        raise MatchInputError('EXPECTED_PERFORMANCE_STORE')
    _prepare(notice, reference_year, top_n, weights, recent_years, category_groups)
    return match_notice(notice, store.search(limit=(1 << 63) - 1), reference_year=reference_year,
                        top_n=top_n, weights=weights, recent_years=recent_years, category_groups=category_groups)
