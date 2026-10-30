# 사업공고 모니터링 시스템 — 개발 마일스톤

> 문서 목적: Codex / Claude Code 등 코딩 LLM이 단계별로 독립적으로 작업하고, 다음 LLM 세션이 결과를 빠르게 검증·인계받을 수 있도록 개발 단계를 정의한다.

---

## 0. 프로젝트 정의

### 0.1 목표

지정된 공고 사이트를 매일 자동 확인하여 신규/수정 공고를 수집하고, Gemini API로 "우리에게 필요한 공고인지" 판별한 뒤 GitHub Pages에서 확인할 수 있는 시스템을 구축한다.

### 0.2 목표 아키텍처

```text
GitHub Actions (매일 자동 실행)
        ↓
사이트별 Scraper
        ↓
공통 Notice 데이터로 정규화
        ↓
기존 데이터와 비교
        ↓
NEW / UPDATED / EXISTING 판정
        ↓
NEW / UPDATED만 Gemini 분석
        ↓
결과 저장(JSON)
        ↓
정적 대시보드 생성
        ↓
GitHub Pages 배포
```

### 0.3 명시적 제외 범위

다음 기능은 현재 프로젝트 범위에서 제외한다.

- Excel Export
- 첨부파일(PDF/HWP/HWPX 등) 본문 분석
- 마감임박(D-1, D-3 등) 계산/알림
- 자체 키워드 점수 기반 적합성 판정
- 유료 서버/DB
- 유료 LLM API 전제
- 이메일/메신저 발송 기능
- CAPTCHA 우회
- 접근통제/서비스 약관을 우회하는 수집 방식

### 0.4 적합성 판정

공고 적합성 판단은 Gemini 무료 티어 API를 사용한다.

원칙:

1. 모든 공고를 매일 Gemini에 보내지 않는다.
2. `NEW` 또는 `UPDATED`인 공고만 분석한다.
3. `content_hash`가 동일하면 기존 Gemini 결과를 재사용한다.
4. API 실패는 전체 수집 실패로 이어지지 않아야 한다.
5. Gemini 응답은 구조화된 JSON으로 저장한다.

---

# 1. LLM 개발 운영 규칙

Codex / Claude Code는 각 마일스톤을 **하나씩** 수행한다.

## 1.1 작업 시작 전 필수 절차

각 마일스톤 시작 시 LLM은 반드시 아래를 확인한다.

```text
1. 이 문서의 현재 마일스톤
2. 이전 마일스톤의 HANDOFF.md 또는 handoff 섹션
3. 현재 repository tree
4. 관련 테스트
5. 미해결 TODO / known issue
```

기존 구현이 있으면 먼저 읽고 재작성보다 확장을 우선한다.

## 1.2 마일스톤 완료 원칙

"코드를 작성했다"는 완료 조건이 아니다.

완료하려면 반드시 다음 네 가지가 존재해야 한다.

```text
IMPLEMENTATION
TEST
VERIFICATION
HANDOFF
```

## 1.3 마일스톤 산출물 공통 규칙

각 마일스톤 종료 시 다음 파일을 갱신한다.

```text
docs/progress/MXX_RESULT.md
docs/progress/CURRENT_STATE.md
```

`MXX_RESULT.md`에는 최소한 아래 항목이 있어야 한다.

```markdown
# MXX Result

## Status
PASS | PARTIAL | FAIL

## Implemented
- ...

## Files Added
- ...

## Files Modified
- ...

## Tests
- command:
- result:

## Manual Verification
- ...

## Acceptance Criteria
- [x] ...
- [ ] ...

## Known Issues
- ...

## Decisions
- ...

## Next Milestone Notes
- ...
```

## 1.4 CURRENT_STATE.md 형식

다음 LLM이 repository를 빠르게 이해할 수 있도록 항상 최신화한다.

```markdown
# Current State

## Last Completed Milestone
MXX

## Current Architecture
...

## Working Features
- ...

## Known Broken / Pending
- ...

## Important Files
- path: purpose

## Test Commands
...

## Environment / Secrets
- GEMINI_API_KEY: required / not required yet

## Next Recommended Action
...
```

## 1.5 소스 코드 원칙

- 사이트별 로직과 공통 로직을 분리한다.
- `main.py`에 사이트별 parsing 로직을 넣지 않는다.
- API Key, ID, Password를 repository에 저장하지 않는다.
- scraper 하나의 실패가 전체 실행을 중단시키지 않도록 한다.
- 동일 데이터를 반복 호출/분석하지 않는다.
- 가능한 경우 HTML DOM 파싱 또는 공개 API를 사용한다.
- Playwright는 requests/API 방식으로 해결되지 않을 때만 사용한다.
- 임시 patch보다 테스트 가능한 구조를 우선한다.

---

# 2. 목표 Repository 구조

프로젝트 진행 과정에서 아래 구조를 목표로 한다.

```text
notice-monitor/
│
├── src/
│   ├── main.py
│   │
│   ├── core/
│   │   ├── models.py
│   │   ├── storage.py
│   │   ├── normalizer.py
│   │   ├── diff.py
│   │   └── logging.py
│   │
│   ├── scrapers/
│   │   ├── base.py
│   │   ├── registry.py
│   │   └── <site>.py
│   │
│   ├── ai/
│   │   ├── gemini.py
│   │   └── relevance.py
│   │
│   └── renderer/
│       └── dashboard.py
│
├── config/
│   ├── sites.yaml
│   └── relevance_policy.yaml
│
├── data/
│   ├── notices.json
│   └── scraper_status.json
│
├── public/
│   └── index.html
│
├── tests/
│   ├── fixtures/
│   └── ...
│
├── docs/
│   ├── site-audit/
│   └── progress/
│
├── .github/
│   └── workflows/
│       └── daily.yml
│
├── requirements.txt
└── README.md
```

실제 구현 과정에서 합리적인 이유가 있으면 구조 변경 가능하다. 변경 이유는 `CURRENT_STATE.md`에 기록한다.

---

# 3. 공통 Notice 데이터 계약

모든 scraper의 최종 결과는 아래 의미를 만족해야 한다.

```yaml
notice_id: string
source_id: string
institution: string
title: string
category: string | null
published_at: string | null
apply_start: string | null
apply_end: string | null
url: string
content_text: string
content_hash: string

status: NEW | UPDATED | EXISTING

gemini:
  status: NOT_ANALYZED | SUCCESS | FAILED | PENDING
  relevant: boolean | null
  score: number | null
  reason: string | null
  category: string | null
  analyzed_at: string | null
  analyzed_content_hash: string | null

first_seen_at: string
last_seen_at: string
updated_at: string
```

### 데이터 계약 원칙

- 날짜는 가능한 경우 ISO 형식으로 정규화한다.
- 값이 없으면 빈 문자열 대신 `null`을 우선한다.
- `url`은 가능한 경우 상세 공고의 canonical URL을 저장한다.
- `content_text`는 첨부파일이 아니라 웹 상세 페이지 본문 기준이다.
- navigation/header/footer/script/style 등은 제거한다.
- `notice_id`는 같은 공고를 여러 실행에서 안정적으로 식별해야 한다.
- `content_hash`는 중요 본문 변경 탐지에 사용한다.

---

# 4. 개발 마일스톤

---

## M00 — Repository Bootstrap

### 목표

LLM 개발을 위한 최소 repository 구조와 문서/테스트 기반을 만든다.

### 입력

- 본 `MILESTONES.md`
- 기존 repository가 있다면 해당 파일들

### 작업

1. 목표 repository 기본 디렉터리 생성
2. Python 프로젝트 최소 실행 구조 생성
3. 테스트 runner 구성
4. `.gitignore` 구성
5. `.env.example` 생성
6. `docs/progress/` 생성
7. README에 프로젝트 목적과 실행 예정 구조 기록

### 산출물

```text
src/
tests/
config/
data/
public/
docs/progress/
.env.example
.gitignore
README.md
requirements.txt 또는 pyproject.toml
```

### 검증

LLM이 실제 명령어를 실행하여 확인한다.

```text
- Python import가 깨지지 않는가
- test runner가 실행되는가
- secret 파일이 git 대상에서 제외되는가
```

### 완료 조건

- [ ] repository 기본 구조 존재
- [ ] 최소 테스트 명령 실행 성공
- [ ] `.env` / secret이 gitignore 처리됨
- [ ] `M00_RESULT.md` 작성
- [ ] `CURRENT_STATE.md` 작성

### 다음 단계 인계 포인트

M01은 코드 개발보다 사이트 조사가 목적이다.

---

## M01 — 전체 사이트 기술 조사 및 Site Inventory

### 목표

모니터링 대상 URL 각각의 기술적 수집 방식을 확정한다.

### 입력

- 원본 모니터링 사이트 목록
- 현재 config/sites.yaml (존재 시)

### 사이트별 조사 항목

```yaml
source_id:
institution:
name:
list_url:
detail_url_pattern:
enabled:
access_status:

content_type:
  - STATIC_HTML
  - JSON_API
  - DYNAMIC
  - LOGIN
  - SPECIAL
  - UNSUPPORTED

pagination:
  type:
  notes:

detail:
  reachable_without_login:
  body_available_in_html:

auth:
  required:
  method:

anti_bot:
  detected:
  notes:

recommended_strategy:
  - REQUESTS
  - API
  - PLAYWRIGHT
  - MANUAL_ONLY

risk:
  level: LOW | MEDIUM | HIGH
  notes:
```

### 작업

각 사이트에 대해:

1. URL 정상 접근 확인
2. 공고 목록 위치 확인
3. 상세페이지 URL 확인
4. 페이지네이션 방식 확인
5. HTML에 데이터가 포함되는지 확인
6. JSON/XHR API 사용 여부 확인
7. JavaScript 렌더링 필요 여부 확인
8. 로그인 필요 여부 확인
9. CAPTCHA/봇 차단 여부 확인
10. 첨부파일 없이 웹 본문만으로 판별 가능한지 확인
11. 추천 수집 전략 지정

### 산출물

```text
docs/site-audit/SITE_INVENTORY.md
config/sites.yaml
docs/progress/M01_RESULT.md
```

`SITE_INVENTORY.md`는 표와 상세 섹션을 함께 사용한다.

### 완료 조건

- [ ] 모든 대상 사이트가 inventory에 존재
- [ ] 모든 사이트에 수집 전략 지정
- [ ] 지원 불가 사이트는 이유 기록
- [ ] HIGH risk 사이트 식별
- [ ] MVP 후보 5개 이상 선정
- [ ] M01_RESULT.md PASS 또는 PARTIAL

### 금지

이 단계에서 전체 scraper 구현을 시작하지 않는다.

---

## M02 — Core Data Model

### 목표

모든 사이트가 공유하는 `Notice` 데이터 모델을 구현한다.

### 작업

1. Notice 모델 정의
2. Gemini 결과 모델 정의
3. serialization/deserialization 정의
4. 필수/선택 필드 결정
5. 날짜 표현 규칙 정의
6. `notice_id` 생성 인터페이스 정의
7. `content_hash` 생성 인터페이스 정의

### 산출물

```text
src/core/models.py
tests/test_models.py
docs/progress/M02_RESULT.md
```

### 테스트 필수 케이스

- 정상 Notice 생성
- optional 필드 null
- JSON round-trip
- status enum 검증
- Gemini status 검증

### 완료 조건

- [ ] Notice 계약이 코드로 고정됨
- [ ] serialization 테스트 통과
- [ ] 이후 scraper가 모델을 import해서 사용할 수 있음

---

## M03 — Normalizer 및 Stable Identity

### 목표

사이트마다 다른 표현을 공통 형식으로 정규화하고 공고 ID를 안정적으로 생성한다.

### 작업

1. 날짜 normalization
2. whitespace normalization
3. 기관명 normalization
4. URL normalization
5. 본문 text cleanup
6. stable `notice_id` 생성
7. `content_hash` 생성

### ID 우선순위

가능하면:

```text
1. 사이트 고유 공고 ID
2. 공고번호
3. 안정적인 상세 URL
4. source_id + normalized title + canonical URL hash
```

### 산출물

```text
src/core/normalizer.py
tests/test_normalizer.py
docs/progress/M03_RESULT.md
```

### 테스트

최소 다음 변형을 fixture로 검증한다.

```text
2026.10.30
2026-10-30
2026년 10월 30일
2026.10.30(금)
```

### 완료 조건

- [ ] 동일 공고가 반복 수집되어도 같은 notice_id
- [ ] 실질 본문이 같으면 같은 content_hash
- [ ] 날짜 normalization 테스트 통과

---

## M04 — Scraper Framework

### 목표

사이트별 scraper를 독립 구현할 수 있는 공통 framework를 만든다.

### 권장 인터페이스

```text
BaseScraper
  fetch_list()
  parse_list()
  fetch_detail()
  parse_detail()
  normalize()
  run()
```

정확한 메서드명은 변경 가능하나 역할 분리는 유지한다.

### 추가 요구사항

- HTTP timeout
- retry 전략
- User-Agent 명시
- 개별 사이트 오류 격리
- scraper 결과/에러 logging
- 사이트별 config 참조

### 산출물

```text
src/scrapers/base.py
src/scrapers/registry.py
tests/test_scraper_base.py
docs/progress/M04_RESULT.md
```

### 완료 조건

- [ ] mock scraper로 end-to-end run 가능
- [ ] 한 scraper 실패가 다른 scraper 실행을 막지 않음
- [ ] 공통 결과가 Notice 리스트임

---

## M05 — MVP Scrapers 5개

### 목표

M01에서 선정한 가장 단순하고 중요한 5개 사이트를 실제 구현한다.

### 사이트 선정 기준

1. 업무 중요도
2. STATIC/API 우선
3. 로그인 불필요
4. 봇 차단 낮음
5. 공고 상세본문 확보 가능

### 각 scraper 필수 산출물

```text
src/scrapers/<source_id>.py
tests/fixtures/<source_id>/
tests/test_<source_id>.py
```

### fixture 원칙

가능하면 실제 응답에서 개인정보/불필요한 요소를 제거한 최소 HTML/JSON fixture를 저장한다.

### 테스트

각 사이트별:

- 목록 parsing
- 상세 URL 생성
- 상세 본문 parsing
- Notice 생성
- 빈 목록 처리
- 예상 selector 미존재 처리

### 완료 조건

- [ ] 5개 사이트 모두 local 실행 성공
- [ ] fixture 기반 테스트 존재
- [ ] 실제 네트워크 smoke test 결과 기록
- [ ] 공고 데이터가 Notice 계약 준수

---

## M06 — Storage Layer

### 목표

서버 DB 없이 repository 기반 JSON 데이터 저장을 안정적으로 구현한다.

### 작업

1. notices load/save
2. scraper status load/save
3. atomic write
4. 파일 손상 방지
5. 초기 빈 데이터 처리
6. deterministic JSON formatting

### 권장 파일

```text
data/notices.json
data/scraper_status.json
```

### 주의

프로세스 중간 실패 시 기존 정상 JSON을 덮어써서 손상시키지 않는다.

### 산출물

```text
src/core/storage.py
tests/test_storage.py
docs/progress/M06_RESULT.md
```

### 완료 조건

- [ ] 빈 저장소에서 최초 실행 가능
- [ ] 저장 후 재로드 동일
- [ ] atomic save 테스트
- [ ] 잘못된 데이터 파일 에러 처리 정의

---

## M07 — NEW / UPDATED / EXISTING 판정

### 목표

오늘 수집 결과와 기존 데이터를 비교한다.

### 상태 의미

```text
NEW
기존 저장소에 없는 notice_id

UPDATED
notice_id는 같지만 content_hash 또는 추적 대상 핵심 필드가 변경됨

EXISTING
기존 데이터와 의미 있는 변경 없음
```

### 작업

1. diff engine 구현
2. 최초/마지막 발견시각 관리
3. UPDATED 판정 규칙 정의
4. 중복 결과 방지
5. 변경된 필드 로그 가능 구조 마련

### 산출물

```text
src/core/diff.py
tests/test_diff.py
docs/progress/M07_RESULT.md
```

### 필수 테스트

- 처음 본 공고 → NEW
- 같은 공고 동일 본문 → EXISTING
- 같은 ID 본문 변경 → UPDATED
- 신규/기존 혼합 batch
- 동일 실행 내 duplicate

### 완료 조건

- [ ] 상태 판정 deterministic
- [ ] 기존 Gemini 결과를 무의미하게 초기화하지 않음
- [ ] UPDATED 시 재분석 필요 여부 판단 가능

---

## M08 — Gemini Relevance Policy

### 목표

"우리에게 필요한 공고" 판정 기준을 코드와 분리된 명시적 정책으로 만든다.

### 작업

`config/relevance_policy.yaml` 작성.

포함 내용:

```yaml
organization_context:
  description: |
    ...

relevant_examples:
  - ...

irrelevant_examples:
  - ...

decision_rules:
  - ...

output_schema:
  relevant: boolean
  score: integer_0_100
  reason: short_string
  category: string
```

### 중요 원칙

이 단계는 Gemini API 연동보다 **판정 기준 고정**이 목적이다.

### 산출물

```text
config/relevance_policy.yaml
docs/relevance-policy.md
docs/progress/M08_RESULT.md
```

### 완료 조건

- [ ] 다른 LLM이 읽어도 판정 기준 이해 가능
- [ ] 명백한 관련/비관련 예시 존재
- [ ] 모호한 경우 처리 규칙 존재
- [ ] 출력 schema 고정

---

## M09 — Gemini Client + Structured Output

### 목표

Gemini API에 공고를 전달하고 구조화 결과를 안정적으로 받는다.

### 환경 변수

```text
GEMINI_API_KEY
```

### 입력 데이터

Gemini에는 필요한 최소 데이터만 전달한다.

```text
institution
title
category
published/apply dates
cleaned content_text
url
relevance policy
```

첨부파일 내용은 사용하지 않는다.

### 출력

```json
{
  "relevant": true,
  "score": 90,
  "reason": "...",
  "category": "..."
}
```

### 요구사항

- timeout
- API 오류 처리
- JSON schema validation
- malformed response 처리
- secret logging 금지
- model name/config 한 곳에서 관리

### 산출물

```text
src/ai/gemini.py
src/ai/relevance.py
tests/test_gemini.py
docs/progress/M09_RESULT.md
```

### 테스트 방식

실제 API 테스트와 mock 테스트를 분리한다.

기본 CI 테스트는 API Key 없어도 실행 가능해야 한다.

### 완료 조건

- [ ] mock 기반 테스트 통과
- [ ] API 실패가 전체 프로그램 중단시키지 않음
- [ ] 구조화 응답만 저장
- [ ] key가 로그에 노출되지 않음

---

## M10 — Gemini Cache / 최소 호출 정책

### 목표

Gemini 무료 티어를 불필요하게 소모하지 않는다.

### 호출 규칙

```text
NEW
→ Gemini 분석

UPDATED && content_hash 변경
→ Gemini 재분석

EXISTING
→ 기존 결과 사용

UPDATED지만 Gemini 분석 대상 내용이 실질적으로 동일
→ 기존 결과 사용 가능
```

### 저장 필드

```text
gemini.analyzed_content_hash
gemini.analyzed_at
gemini.status
```

### 산출물

```text
src/ai/relevance.py 업데이트
tests/test_relevance_cache.py
docs/progress/M10_RESULT.md
```

### 완료 조건

- [ ] 동일 공고 반복 실행 시 API 재호출 없음
- [ ] 본문 변경 시 재분석
- [ ] FAILED/PENDING 상태 재시도 정책 명시

---

## M11 — End-to-End Local Pipeline

### 목표

로컬 한 번 실행으로 MVP 전체 흐름을 연결한다.

### 실행 흐름

```text
config load
→ scraper run
→ normalize
→ storage load
→ diff
→ Gemini 대상 선택
→ Gemini 분석
→ storage save
→ status save
```

### 산출물

```text
src/main.py
tests/test_pipeline.py
docs/progress/M11_RESULT.md
```

### 실행 인터페이스 예시

```bash
python -m src.main
```

또는 프로젝트 구조에 맞는 단일 명령.

### 완료 조건

- [ ] 5개 MVP 사이트 pipeline 실행
- [ ] 한 사이트 실패해도 나머지 진행
- [ ] 결과 JSON 생성
- [ ] 두 번째 실행에서 불필요한 Gemini 재호출 없음
- [ ] 로그만 보고 성공/실패 사이트 식별 가능

---

## M12 — Scraper Status / Observability

### 목표

"공고가 없는 것"과 "scraper가 깨진 것"을 구분할 수 있게 한다.

### 사이트별 상태 예시

```yaml
source_id:
  status: SUCCESS | ERROR | WARNING
  last_attempt_at:
  last_success_at:
  notices_found:
  error_type:
  error_message:
```

### 경고 후보

- selector not found
- HTTP 403/429
- timeout
- JSON schema 변경
- 이전에는 데이터가 있었는데 갑자기 0건
- login required 변화

### 산출물

```text
data/scraper_status.json
관련 core 코드
tests/test_scraper_status.py
docs/progress/M12_RESULT.md
```

### 완료 조건

- [ ] 모든 scraper 실행 결과 기록
- [ ] 에러 메시지가 원인 파악에 충분
- [ ] secret/민감정보는 로그에 없음

---

## M13 — GitHub Pages Dashboard

### 목표

JSON 결과를 사람이 쉽게 확인할 정적 웹페이지로 만든다.

### 기본 화면 필수 요소

```text
마지막 업데이트 시각
수집 성공/실패 요약

관련 공고 기본 보기
NEW / UPDATED 상태
Gemini score
기관
공고 제목
Gemini 판정 이유
원문 링크

전체 공고 보기 전환
```

### 기본 정책

첫 화면은 가능하면 `gemini.relevant == true` 결과를 중심으로 보여준다.

### 필요 없는 기능

- Excel 다운로드
- 첨부파일 분석 UI
- 마감임박 UI

### 산출물

```text
src/renderer/dashboard.py
public/index.html
필요한 static assets
tests/test_dashboard.py
docs/progress/M13_RESULT.md
```

### 완료 조건

- [ ] 정적 파일만으로 열림
- [ ] 관련 공고 확인 가능
- [ ] NEW / UPDATED 구분
- [ ] 원문 링크 정상
- [ ] Gemini 실패 공고도 숨겨지지 않고 상태 확인 가능

---

## M14 — GitHub Actions Daily Automation

### 목표

PC가 꺼져 있어도 GitHub에서 매일 자동 실행되게 한다.

### Workflow 책임

```text
checkout
Python setup
dependency install
scraper pipeline
dashboard generation
data/public 변경 commit
GitHub Pages 배포
```

### Secret

```text
GEMINI_API_KEY
```

### 권장

한국 시간 아침 실행. 정각보다 약간 어긋난 시간 사용을 고려한다.

### 추가 기능

`workflow_dispatch`를 제공해 수동 실행 가능하게 한다.

### 산출물

```text
.github/workflows/daily.yml
README 배포/secret 설정 문서
docs/progress/M14_RESULT.md
```

### 완료 조건

- [ ] manual workflow 실행 성공
- [ ] Gemini secret 접근 성공
- [ ] data 갱신 확인
- [ ] public 갱신 확인
- [ ] Pages 접근 확인
- [ ] workflow failure 로그로 원인 확인 가능

---

## M15 — MVP 7-Day Stability Gate

### 목표

기능 추가보다 운영 안정성을 검증한다.

### 검증 기간

7회 이상의 일일 실행 결과를 기준으로 판단한다.

### 기록할 항목

```text
날짜
workflow 성공/실패
사이트별 성공률
신규 공고 수
수정 공고 수
Gemini 호출 수
Gemini 실패 수
scraper 오류
수동 수정 여부
```

### 산출물

```text
docs/mvp-stability-report.md
docs/progress/M15_RESULT.md
```

### PASS 기준

- [ ] 7회 자동 실행 기록
- [ ] 전체 pipeline 데이터 손상 없음
- [ ] 중복 폭증 없음
- [ ] Gemini 반복 호출 버그 없음
- [ ] 주요 5개 scraper 안정적
- [ ] 실패 원인 추적 가능

PASS 이후에만 사이트 확대를 권장한다.

---

## M16 — 일반 사이트 확대

### 목표

MVP 이후 LOW/MEDIUM risk 사이트를 단계적으로 추가한다.

### 개발 단위

한 번에 최대 3~5개 사이트를 추가한다.

각 batch마다:

```text
scraper 구현
fixture
unit test
network smoke test
pipeline test
M16_BATCH_N_RESULT.md
```

### 완료 조건

각 사이트가 최소:

- [ ] 목록 parsing
- [ ] 상세 parsing
- [ ] Notice normalization
- [ ] error handling
- [ ] fixture test

를 갖는다.

---

## M17 — Dynamic / JavaScript 사이트

### 목표

requests/API만으로 처리할 수 없는 중요한 사이트를 지원한다.

### 우선순위

항상 다음 순서를 따른다.

```text
공개 JSON/API 탐색
↓
requests 방식
↓
Playwright
```

### Playwright 사용 시 추가 요구사항

- 브라우저 timeout
- selector wait 전략
- screenshot/debug artifact 정책
- GitHub Actions 실행 검증
- browser dependency 문서화

### 산출물

사이트별 scraper/test/fixture + 결과 문서.

### 완료 조건

- [ ] GitHub Actions 환경에서 재현 가능
- [ ] 무한 wait 없음
- [ ] 실패가 전체 pipeline을 중단시키지 않음

---

## M18 — Login / Special Sites

### 목표

업무상 반드시 필요한 로그인/특수 시스템만 선별적으로 지원한다.

### 원칙

- 로그인 없이 접근 가능한 공개 공고 경로를 먼저 찾는다.
- credentials는 GitHub Secrets만 사용한다.
- CAPTCHA 우회는 하지 않는다.
- 세션/토큰이 불안정하면 `MANUAL_ONLY` 상태를 허용한다.
- 유지보수 비용이 지나치게 높은 사이트는 자동화 제외 가능하다.

### 산출물

각 사이트별:

```text
implementation or MANUAL_ONLY decision
security notes
test strategy
M18_<site>_RESULT.md
```

### 완료 조건

자동화 여부가 명확하게 결정되어 있어야 한다. "미정"으로 끝내지 않는다.

---

## M19 — Full Regression / Hardening

### 목표

전체 사이트 확대 후 회귀 버그와 운영 리스크를 정리한다.

### 필수 시나리오

```text
사이트 하나 timeout
사이트 하나 403
HTML selector 변경
Gemini 429
Gemini malformed response
JSON 파일 없음
JSON 파일 일부 손상
동일 workflow 재실행
공고 0건
동일 공고 duplicate
공고 본문 수정
```

### 추가 점검

- logging 품질
- dependency pinning
- secret 노출 여부
- 파일 크기 증가
- GitHub Actions 실행시간
- Pages 생성시간

### 산출물

```text
docs/regression-report.md
docs/progress/M19_RESULT.md
```

### 완료 조건

- [ ] 주요 failure scenario 테스트
- [ ] 치명적 데이터 손상 경로 없음
- [ ] 복구 절차 문서화
- [ ] known issue 목록 최신화

---

## M20 — Production Baseline

### 목표

"완성" 상태를 정의하고 향후 유지보수 기준선을 만든다.

### 최종 산출물

```text
README.md
docs/ARCHITECTURE.md
docs/OPERATIONS.md
docs/SITE_SUPPORT_MATRIX.md
docs/progress/CURRENT_STATE.md
```

### SITE_SUPPORT_MATRIX 예시

| Source | Strategy | Status | Last Verified | Test | Notes |
|---|---|---|---|---|---|
| site-a | requests | SUPPORTED | YYYY-MM-DD | PASS | |
| site-b | api | SUPPORTED | YYYY-MM-DD | PASS | |
| site-c | playwright | DEGRADED | YYYY-MM-DD | PASS | selector fragile |
| site-d | manual | MANUAL_ONLY | YYYY-MM-DD | N/A | CAPTCHA |

### Production Baseline 완료 조건

- [ ] 지원 사이트 목록 명확
- [ ] 매일 GitHub Actions 자동 실행
- [ ] Gemini 분석 캐시 정상
- [ ] GitHub Pages 정상
- [ ] 장애 확인 방법 문서화
- [ ] 신규 개발자가 CURRENT_STATE만 읽고 시작 가능

---

# 5. 마일스톤 실행 우선순위

## Phase A — Foundation

```text
M00
M01
M02
M03
M04
```

## Phase B — MVP Collection

```text
M05
M06
M07
```

## Phase C — AI Filtering

```text
M08
M09
M10
```

## Phase D — End-to-End MVP

```text
M11
M12
M13
M14
M15
```

## Phase E — Expansion

```text
M16
M17
M18
```

## Phase F — Stabilization

```text
M19
M20
```

---

# 6. LLM용 마일스톤 시작 프롬프트 템플릿

Codex / Claude Code에 각 단계를 맡길 때 아래 형식을 사용할 수 있다.

```text
현재 repository에서 MILESTONES.md의 [MXX — 마일스톤명]만 수행해.

작업 전 반드시:
1. MILESTONES.md의 전체 프로젝트 규칙과 해당 MXX를 읽고,
2. docs/progress/CURRENT_STATE.md와 직전 RESULT 문서를 읽고,
3. 현재 코드/테스트 구조를 조사해.

중요:
- 다음 마일스톤 작업을 선행해서 구현하지 마.
- 기존 구조가 합리적이면 유지하고 확장해.
- 실제 테스트 명령을 실행해.
- 실패한 테스트가 있으면 원인을 해결하거나 명시적으로 기록해.
- 완료 후 docs/progress/MXX_RESULT.md를 작성해.
- docs/progress/CURRENT_STATE.md를 최신 상태로 갱신해.
- Acceptance Criteria를 하나씩 PASS/FAIL로 확인해.
- 최종 응답에는 변경 파일, 실행한 테스트, 남은 문제만 요약해.
```

---

# 7. LLM용 검토 전용 프롬프트 템플릿

구현 LLM과 검토 LLM을 분리하고 싶다면 다음 형식을 사용한다.

```text
MILESTONES.md의 [MXX] Acceptance Criteria를 기준으로 현재 구현을 검토해.

코드를 새로 설계하거나 대규모 리팩터링하기 전에 먼저 검증해.

검토 절차:
1. docs/progress/MXX_RESULT.md를 읽어.
2. 실제 변경 파일을 확인해.
3. 관련 테스트를 직접 실행해.
4. Acceptance Criteria 각각에 대해 PASS/FAIL 근거를 제시해.
5. 문서에 적힌 주장과 실제 repository 상태가 다른지 확인해.
6. 보안/secret 노출 여부를 확인해.
7. 다음 마일스톤을 진행해도 되는지 판정해.

결과는 다음 형식으로 작성해:

STATUS: PASS | FAIL

CRITERIA:
- [PASS] ...
- [FAIL] ...

BLOCKERS:
- ...

NON-BLOCKING:
- ...

RECOMMENDATION:
PROCEED_TO_NEXT_MILESTONE | FIX_CURRENT_MILESTONE
```

---

# 8. Stop Conditions

다음 상황에서는 억지로 다음 마일스톤으로 진행하지 않는다.

```text
핵심 테스트 실패
데이터 손상 가능성
secret 노출
동일 공고가 계속 NEW로 잡힘
Gemini가 같은 공고에 매 실행마다 호출됨
한 scraper 실패로 전체 pipeline 종료
사이트 조사 없이 Playwright부터 도입
MVP 안정성 검증 없이 전체 사이트 확대
```

---

# 9. Definition of Done

이 프로젝트의 완료는 단순히 "모든 사이트 scraper 코드가 존재함"을 의미하지 않는다.

다음 상태를 최종 완료로 본다.

```text
1. 지원 대상 사이트가 명확히 문서화됨
2. 매일 GitHub Actions 자동 실행
3. 신규/수정 공고 자동 판별
4. Gemini가 신규/수정 공고만 분석
5. 동일 본문 재분석 방지
6. Gemini 실패가 수집을 막지 않음
7. scraper 하나의 장애가 전체를 막지 않음
8. GitHub Pages에서 관련 공고 확인 가능
9. 사이트별 마지막 성공/실패 상태 확인 가능
10. 다음 LLM이 CURRENT_STATE.md만 읽고 유지보수 가능
```

---

# 10. 현재 권장 시작점

첫 실행은 `M00 → M01`까지만 진행한다.

특히 M01에서 전체 사이트를 기술적으로 분류하기 전에 특정 사이트 scraper를 대량 구현하지 않는다.

M01의 `SITE_INVENTORY.md`가 이후 개발의 사실상 설계 기준 문서가 된다.
