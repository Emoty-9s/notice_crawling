# M14 Result

## Status

**PASS (로컬 규칙/오프라인 검증)** — MILESTONES_V2.md M14 Local Performance Matcher.
검증일: 2026-11-02 (Asia/Seoul). 가중치 기반 TOP N/점수 근거/결정성/중복 방지 및 전체 회귀 검증 완료.
M15 UI는 구현하지 않았다. 기존 M11 배포 및 M12 실제 원격 다운로드의 미검증 상태는 그대로다.

## Implementation / Files

생성: src/local_client/matcher.py, tests/test_matcher.py, docs/progress/M14_RESULT.md.
수정: README.md, docs/progress/CURRENT_STATE.md.

기존 중앙 pipeline/AI/feed/Actions, M12 sync/CLI/cache 및 M13 Performance/SQLite/CSV 계약은 변경하지 않았다.
새 매칭 모듈은 stdlib와 로컬 Performance/PerformanceStore만 사용한다. 네트워크/Gemini/embedding/시계 호출이 없다.
실적과 추천 결과를 저장/업로드하거나 public feed에 추가하지 않는다. 테스트도 임시 DB/합성 실적만 사용했다.

## API / Handoff

```python
from src.local_client.matcher import MatchWeights, match_notice, match_store

# snapshot은 M12 FeedClient.load_cache()의 검증된 반환값이다.
notice = snapshot['feed']['notices'][0]

# 이미 읽은 Performance iterable을 평가하는 순수 함수
results = match_notice(notice, performances, reference_year=2026, top_n=5)

# 기존 PerformanceStore에서 모든 실적을 한 SELECT로 읽고 평가
results = match_store(notice, store, reference_year=2026, top_n=5)

# 모든 점수 가중치는 matcher.py의 MatchWeights 한 곳에 있다.
custom = MatchWeights(keyword=3, title=0)
results = match_store(notice, store, reference_year=2026, weights=custom)
payload = [result.to_dict() for result in results]
```

입력은 M12 feed의 **개별 notice dict**다. 사용하는 필드는 category/participation_type/keywords/title/summary다.
feed envelope나 중앙 Notice를 입력하지 않는다. M12 schema 검증 계약을 바꾸거나 실적 DB에 공고 필드를 추가하지 않는다.
반환은 MatchResult 목록이며 performance_id/score/matched_terms/reasons를 가진다. to_dict()는 로컬 JSON용 dict를 반환한다.
reasons에는 rule/points/terms가 있으며 합계가 score다. 원본 고객명/변리사/메모/전체 실적을 결과에 복사하지 않는다.

## Default Scoring Contract

공개 notice에는 별도 technical_field/work_type이 없으므로 아래 로컬 규칙으로 근거를 찾는다.
문자 정규화는 Unicode NFKC → casefold → 대시 통일 → 연속 공백 축약이다.
용어/문구는 한 필드 안에서 Unicode 영숫자 경계를 기준으로 일치해야 한다.
예: AI는 chair와, 반도체는 반도체장비와 일치하지 않는다. 여러 단어인 기술분야는 문구 그대로 비교한다.

| 규칙 | 기본 점수 | 조건/횟수 |
| --- | --- | --- |
| technical_field | +5 | 실적 technical_field가 notice의 category/participation_type/title/summary/keywords에 정확한 용어·문구로 등장, 1회 |
| work_type | +5 | 실적 work_type이 위 notice 필드에 정확한 용어·문구로 등장, 1회 |
| keyword | +2/개 | 고유 notice keyword가 실적 technical_field/work_type/keywords/project_name/description에 등장 |
| category | +3 | notice category와 실적 technical_field/work_type/keyword의 정확 일치 또는 명시된 category 관계 그룹, 1회 |
| title | +2 | notice title과 실적 project_name에 공통 핵심 token이 하나 이상 있음, token 수와 무관하게 1회 |
| recent | +1 | 0 <= reference_year - 실적 year < recent_years, 1회 |

- category 관계는 matcher.py의 DEFAULT_CATEGORY_GROUPS에 명시한다. 예: IP-R&D ↔ 특허분석/특허전략.
  category_groups 인자로 교체할 수 있고 빈 tuple이면 관계 그룹만 끈다(정확 일치는 유지).
- 제목 token은 한글/영숫자 및 내부 `-`, `&` 조합이다. 1글자/숫자 연도/공고·모집 등 TITLE_STOPWORDS를 제외한다.
- 최근 실적 기본 recent_years=3은 기준 연도와 이전 2년이다. 미래/미상 연도는 0점, recent_years=0은 비활성이다.
- 기준 연도 reference_year는 **필수 인자**다. 내부에서 현재 연도를 읽지 않아 동일 입력 결과가 달라지지 않는다.
- 고객명/client, attorneys, notes는 점수에 사용하지 않는다.

## Duplicate / Ranking / Explanation Contract

양쪽 keywords를 정규화 후 집합으로 처리한다. 공백/대소문자/한글 조합형/전각/대시 표기만 다른 동일어는 한 번만 계산한다.
같은 단어가 여러 필드나 본문에 반복돼도 keyword 점수는 한 번이다. category/title 보너스도 각각 1회다.
서로 다른 규칙의 근거가 같은 것은 허용한다. 예를 들어 기술분야 반도체 일치 +5와 keyword 반도체 일치 +2는 별도 가중치다.
동의어/서로 다른 복합어를 자동 통합하지는 않는다.

matched_terms는 점수가 발생한 규칙의 정규화된 용어를 중복 제거/정렬한 tuple이다. 최근 연도는 이 목록에서 제외하고 recent reason에만 표시한다.
0 가중치 규칙은 점수와 근거 목록에서 제외한다. 모든 가중치는 bool/float를 제외한 0 이상 int다.
표준 예시(관련 실적 year=2025, 기준=2026): 5+5+3개 keyword 6+category 3+title 2+recent 1 = **22점**이다.

정렬은 **score 내림차순 → performance_id 오름차순**이다. 입력 실적/keyword 순서에 영향을 받지 않는다.
top_n 기본 5, 0은 빈 목록, DB 크기보다 크면 전부 반환한다. bool/음수는 오류다.
0점/최근 보너스만 있는 약한 결과도 포함하므로 점수를 함께 확인해야 한다. 참여 자격 확정이나 확률 점수가 아니다.
중복 performance_id 입력은 동일 record여도 MatchInputError다. 임의 승자를 선택하거나 중복 추천하지 않는다.

match_store는 기존 search 기본값 100에 잘리지 않도록 SQLite의 최대 LIMIT로 전체 실적을 한 번에 읽는다.
DB/cache를 변경하지 않으며 DB 오류는 그대로 전파한다. 손상 DB를 정상 빈 추천으로 숨기지 않는다.

## Tests / Actual Results

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_matcher.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

M14 신규 **27 tests OK**. 전체 **328 tests OK**(기존 301 + 신규 27), 실패/오류 0, exit code 0.

검증: 정확한 기본 점수/근거 합계, 동일 입력·순서 변경 결정성, 관련/부분 관련/무관 순위,
키워드 반복/공백/대소문자 중복 방지, 한글 조합형/전각 정규화, 다중어 문구/부분문자열 경계,
제목 횟수 상한/일반어 제외, 업무유형 일치, category 정확·관계 그룹/중복 상한/사용자 설정,
최근 연도 경계/미래/미상/기준 창 변경, 동점/빈 iterable·DB/TOP N, 가중치 변경·비활성,
입력 불변/JSON 결과/개인 필드 미복사/오류 입력/중복 ID,
100건을 넘는 DB 전체 평가 및 실제 M09 생성 → M12 mock cache → M13 DB → M14 로컬 매칭 통합.
실제 HTTP와 Gemini 호출을 금지한 상태에서 통합 점수 22점을 확인했고, 전후 DB/cache bytes도 동일했다.

## Blocker / Limits / Next

- M14 구현 blocker 없음. 외부 API/Secret/추가 패키지가 필요 없다.
- 형태소 분석/embedding/임의 동의어 추론은 없다. 조사/띄어쓰기/미등록 업종 표현은 일치하지 않을 수 있다.
- category 관계와 제목 제외어는 초기 명시적 규칙이다. 실제 로컬 표본으로 가중치/규칙을 조정할 수 있다.
- 전체 실적을 메모리에 읽고 평가한다. 대규모 DB 최적화/결과 영속 저장/CLI/UI는 추가하지 않았다.
- M11 배포 URL/M12 실제 원격 다운로드 검증은 별도로 남아 있다.

다음: 사용자 로컬 공고·실적 표본으로 추천 근거와 가중치를 검토할 수 있다. M15 UI는 사용자 요청 전 착수하지 않는다.
