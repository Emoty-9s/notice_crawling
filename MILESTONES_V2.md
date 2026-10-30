# 사업공고 모니터링 시스템 — MILESTONES v2

> 목표: 먼저 개인용 v1을 완성해 실제로 충분히 사용해 본 뒤, 판매용 기능은 별도 v2 프로젝트에서 검토한다.
>
> 현재 핵심 구조:
>
> 중앙 GitHub → 공고 수집 → 신규/수정 판정 → Gemini가 “특허법인이 참여 가능한 공고인지” 판정 → 관련 공고만 JSON 배포  
> 로컬 PC → JSON 다운로드 → 로컬 실적 DB와 매칭 → 유사실적 표시 → 로컬 화면

---

# 0. 프로젝트 범위

## 개인용 v1의 Definition of Done

다음이 모두 되면 이번 프로젝트를 완료로 본다.

1. 지정 사이트의 공고를 자동 수집한다.
2. 신규/수정 공고를 구분한다.
3. Gemini가 특허법인/특허사무소가 참여 가능한 공고인지 중앙에서 한 번 판정한다.
4. 관련 공고만 공통 JSON으로 생성한다.
5. GitHub를 통해 JSON을 배포한다.
6. 내 PC의 로컬 클라이언트가 JSON을 자동으로 내려받는다.
7. 내 실적 데이터는 로컬 PC에만 저장한다.
8. 공고와 내 실적을 규칙 기반으로 매칭한다.
9. 공고별 유사실적 TOP N을 화면에서 확인할 수 있다.
10. 몇 주 이상 실제 사용하면서 문제점을 수정할 수 있는 상태가 된다.

## 이번 버전에서 제외

- 판매용 라이선스
- 고객별 계정/로그인
- 멀티테넌트 서버
- 회사별 중앙 DB
- 고객별 Gemini 호출
- 이메일/메신저 자동 알림
- 담당자 지정/협업 기능
- 결제
- 자동 업데이트 배포
- 판매용 설치 프로그램
- 고객별 맞춤 사이트 관리 UI
- 중앙 서버에 고객 실적 업로드

판매용 기능은 개인용 v1 검증 후 별도 프로젝트로 진행한다.

---

# 1. 공통 개발 운영 규칙

각 마일스톤은 하나씩 수행한다.

시작 전:

1. `MILESTONES_V2.md`의 해당 마일스톤
2. `docs/progress/CURRENT_STATE.md`
3. 직전 `MXX_RESULT.md`
4. 관련 코드와 테스트

를 먼저 읽는다.

각 마일스톤 완료 시:

- `docs/progress/MXX_RESULT.md`
- `docs/progress/CURRENT_STATE.md`

를 갱신한다.

완료 기준은 코드 작성이 아니라:

```text
IMPLEMENTATION
TEST
VERIFICATION
HANDOFF
```

가 모두 존재하는 것이다.

외부 네트워크가 필요한 기능은 unit test와 분리한다.

---

# 2. 현재까지 완료된 마일스톤

## M00 — Repository Bootstrap ✅

목표:

- Python 프로젝트 기본 구조
- 가상환경
- unittest 기반 테스트
- README
- 진행 문서 구조

현재 상태: 완료.

---

## M01 — Site Inventory ✅

목표:

- 원본 XLSB 모니터링 목록 추출
- 대상 URL 조사
- 사이트 분류
- 수집 전략 결정
- MVP 대상 선정

현재 상태: 완료.

주요 산출물:

```text
docs/site-audit/SITE_INVENTORY.md
config/sites.yaml
```

---

## M02 — Core Data Model ✅

목표:

- `Notice`
- Gemini 분석 결과
- status enum
- JSON serialization/deserialization

현재 상태: 완료.

---

## M03 — Normalizer / Stable Identity ✅

목표:

- 날짜 정규화
- 텍스트 정리
- URL 정규화
- stable `notice_id`
- `content_hash`

현재 상태: 완료.

---

## M04 — Scraper Framework ✅

목표:

- 공통 scraper lifecycle
- timeout / retry
- User-Agent
- registry
- scraper별 실패 격리

현재 상태: 완료.

---

## M05 — MVP Scrapers ✅

현재 구현 대상:

- KHIDI
- 창업진흥원 공개 입찰
- 농촌진흥청 입찰
- 서울 R&D
- KIPA 입찰

실제 HTML fixture 기반 parsing 테스트 완료.

현재 상태: 완료.

---

## M06 — Storage Layer ✅

목표:

- JSON load/save
- atomic write
- notices 저장
- scraper status 저장
- malformed data 처리

현재 상태: 완료된 것으로 간주하고 이후 단계에서 인터페이스를 재사용한다.

---

## M07 — NEW / UPDATED / EXISTING 판정 ✅

목표:

- 신규 공고 탐지
- 수정 공고 탐지
- 기존 공고 유지
- 변경 시 Gemini 재분석 여부 판단 가능 구조

현재 상태: 완료.

---

# 3. 개인용 v1 신규 마일스톤

---

# M08 — 중앙 Gemini 공고 적합성 판정

## 목표

신규/수정 공고 중에서:

> “특허법인 또는 특허사무소가 수행기관, 협력기관, 입찰 참여자, 용역 수행자 등의 자격으로 참여할 수 있는 공고인가?”

를 Gemini가 중앙에서 한 번만 판정한다.

고객별/회사별 판단은 하지 않는다.

## 핵심 원칙

Gemini의 역할은:

```text
이 공고가 특허법인 업계의 업무 대상인가?
```

만 판단하는 것이다.

다음은 Gemini가 판단하지 않는다.

```text
우리 회사가 잘할 수 있는가?
우리 회사 실적과 맞는가?
우리 회사가 지원할 것인가?
```

이 판단은 로컬 프로그램의 실적 매칭/사용자 검토 영역이다.

## 입력

최소한:

```text
institution
title
category
published_at
apply_start
apply_end
content_text
url
```

## 출력

구조화된 JSON:

```json
{
  "relevant": true,
  "category": "IP-R&D",
  "participation_type": "협력기관",
  "reason": "특허법인이 협력기관으로 참여 가능한 공고",
  "keywords": [
    "반도체",
    "IP-R&D",
    "특허분석",
    "IP전략"
  ]
}
```

## 구현

권장:

```text
config/relevance_policy.yaml
src/ai/gemini.py
src/ai/relevance.py
tests/test_gemini.py
```

## 캐시 정책

```text
NEW
→ 분석

UPDATED + content_hash 변경
→ 재분석

EXISTING
→ 기존 결과 재사용
```

`analyzed_content_hash`를 저장한다.

## 실패 처리

Gemini 실패가 전체 pipeline을 중단시키면 안 된다.

상태:

```text
SUCCESS
FAILED
PENDING
```

## 테스트

- mock Gemini 정상 응답
- relevant true/false
- malformed JSON
- timeout
- 동일 content_hash 재호출 방지
- 변경된 content_hash 재분석

## 완료 조건

- [ ] 중앙 판정 기준이 명확함
- [ ] 구조화 결과 저장
- [ ] EXISTING 재분석 없음
- [ ] Gemini 실패가 crawler/storage를 중단시키지 않음
- [ ] 실제 API 없이 unit test 가능

---

# M09 — Public Notice Feed JSON

## 목표

Gemini 판정 결과 중 특허법인에 관련된 공고만 모아:

```text
public/notices.json
```

을 생성한다.

이 파일은 이후 모든 로컬 클라이언트가 받는 **공통 배포 데이터**다.

## 포함 대상

기본적으로:

```text
gemini.status == SUCCESS
gemini.relevant == true
```

인 공고.

FAILED/PENDING을 별도 diagnostics JSON에 둘 수 있지만, 일반 feed에는 넣지 않아도 된다.

## Public JSON 필드

최소 권장:

```yaml
schema_version:
generated_at:

notices:
  - notice_id:
    source_id:
    institution:
    title:
    category:
    participation_type:
    published_at:
    apply_start:
    apply_end:
    url:
    summary:
    keywords:
    relevance_reason:
    first_seen_at:
    updated_at:
```

## 중요

`content_text` 전체를 그대로 배포하지 않아도 된다.

로컬 매칭과 화면 표시에 필요한 최소 데이터만 배포한다.

필요하면 `summary`를 생성하되, 초기 버전에서는 기존 본문 일부를 정리한 텍스트여도 된다.

## 추가 산출물

권장:

```text
public/metadata.json
```

예:

```json
{
  "schema_version": 1,
  "generated_at": "...",
  "notice_count": 17
}
```

## 테스트

- relevant 공고만 포함
- irrelevant 제외
- deterministic JSON
- 동일 입력 → 동일 notice data
- required field 존재
- schema_version 존재
- 빈 결과 처리

## 완료 조건

- [ ] `public/notices.json` 생성
- [ ] relevant 공고만 배포
- [ ] schema version 존재
- [ ] 로컬 프로그램이 독립적으로 읽을 수 있는 형태

---

# M10 — Central End-to-End Pipeline

## 목표

중앙 시스템 전체 흐름을 하나의 명령으로 연결한다.

## 흐름

```text
site config load
→ scraper registry 실행
→ normalize
→ 기존 storage load
→ NEW / UPDATED / EXISTING 판정
→ NEW/UPDATED Gemini 판정
→ storage save
→ public/notices.json 생성
→ scraper status save
```

## 실행 예

```powershell
.\.venv\Scripts\python.exe -m src.main
```

## 요구사항

- 사이트 하나 실패해도 나머지 계속
- Gemini 실패해도 나머지 계속
- 기존 정상 데이터 보존
- 두 번째 실행에서 중복 증가 없음
- EXISTING 공고 Gemini 재호출 없음
- JSON feed 생성 성공

## 테스트

fixture + fake Gemini + temporary storage로 end-to-end 테스트한다.

외부 네트워크 없이 전체 pipeline 테스트 가능해야 한다.

## 완료 조건

- [ ] 단일 명령 실행
- [ ] scraper → diff → Gemini → feed 연결
- [ ] 반복 실행 안정성
- [ ] 실패 격리
- [ ] feed 생성

---

# M11 — GitHub Repository / Daily Automation / JSON 배포

## 목표

중앙 pipeline을 GitHub에서 매일 자동 실행하고 `notices.json`을 HTTP로 받을 수 있게 한다.

## 이 단계에서 처음 GitHub 연결

이전 로컬 개발 과정에서 Git을 필수로 사용하지 않았으므로, 여기에서 실제 GitHub repository를 연결한다.

## 작업

1. GitHub repository 생성/연결
2. 필요한 secret 등록
3. GitHub Actions daily workflow
4. manual `workflow_dispatch`
5. pipeline 실행
6. 결과 JSON 배포
7. public URL 확보

## Gemini Secret

예:

```text
GEMINI_API_KEY
```

코드/JSON/repository에 API Key를 저장하지 않는다.

## 배포 방식

가장 단순한 방식 우선:

```text
GitHub Pages
```

에서:

```text
/notices.json
/metadata.json
```

을 정적으로 제공한다.

대시보드 자체는 중앙에 필요하지 않다.

## GitHub Actions 흐름

```text
checkout
→ Python setup
→ pipeline 실행
→ data/public 갱신
→ JSON 배포
```

## 완료 조건

- [ ] 수동 workflow 성공
- [ ] daily schedule 존재
- [ ] Gemini secret 정상 사용
- [ ] public notices.json URL 접근 가능
- [ ] metadata.json 접근 가능
- [ ] 같은 feed를 여러 클라이언트가 받을 수 있음

---

# M12 — Local Client / Feed Sync

## 목표

내 PC의 프로그램이 GitHub에 배포된 `notices.json`을 받아 로컬에 저장한다.

## 역할

```text
GitHub notices.json
        ↓
Local Client
        ↓
local cache
```

## 로컬 구조 예시

```text
local/
  cache/
    notices.json
    metadata.json
```

또는 사용자 데이터 경로에 저장한다.

실제 위치는 OS/프로젝트 구조에 맞게 결정한다.

## 기능

1. remote metadata 확인
2. 새 feed 다운로드
3. schema_version 확인
4. JSON validation
5. atomic local save
6. 다운로드 실패 시 마지막 정상 cache 사용

## 중요

인터넷이 끊겨도 마지막 정상 feed를 볼 수 있어야 한다.

## 테스트

- 정상 다운로드 mock
- malformed JSON
- schema version unsupported
- network timeout
- 기존 cache fallback
- atomic save
- 같은 feed 재다운로드 처리

## 완료 조건

- [ ] public feed 다운로드 가능
- [ ] 로컬 cache 저장
- [ ] 네트워크 실패 fallback
- [ ] 중앙 코드와 로컬 코드 역할 분리

---

# M13 — Local Performance Database

## 목표

내 실적 데이터를 PC 내부에만 저장하고 관리한다.

## 저장 방식

SQLite 권장:

```text
local/performance.db
```

## 실적 데이터 최소 필드

```yaml
performance_id:
project_name:
client:
year:
technical_field:
work_type:
keywords:
description:
attorneys:
notes:
```

필요에 따라:

```text
contract_period
amount
result
```

등을 나중에 추가할 수 있다.

## 중요 원칙

- 실적 데이터는 중앙 GitHub에 업로드하지 않는다.
- Gemini에 전체 실적 DB를 보내지 않는다.
- 로컬에서만 저장/검색/매칭한다.

## 초기 입력

초기 버전에서는 최소 하나 지원:

```text
CSV import
```

또는 현재 보유 실적 형식이 명확하다면 해당 파일 import.

개인용 v1에서 복잡한 입력 UI는 필수가 아니다.

## 기능

- create
- read
- update
- delete
- import
- 검색

## 테스트

- DB 최초 생성
- insert/read/update/delete
- duplicate 처리
- CSV import
- 잘못된 row 처리
- DB 재실행 지속성

## 완료 조건

- [ ] 로컬 DB 생성
- [ ] 실적 등록 가능
- [ ] 실적 검색 가능
- [ ] import 가능
- [ ] 중앙으로 실적 유출 없음

---

# M14 — Local Performance Matcher

## 목표

공고와 로컬 실적을 AI 없이 규칙 기반으로 매칭해 유사실적 TOP N을 추천한다.

## 기본 원칙

초기 버전은:

```text
키워드 + 태그 + 가중치
```

방식을 사용한다.

Gemini 또는 embedding은 사용하지 않는다.

## 매칭 입력

공고:

```text
category
participation_type
keywords
title
summary
```

실적:

```text
technical_field
work_type
keywords
project_name
description
year
```

## 초기 scoring 예

실제 사용하면서 변경 가능하다.

```text
기술분야 정확 일치        +5
업무유형 일치            +5
공고 keyword 일치         +2 / 개
category 관련             +3
최근 실적                 +1
제목 핵심어 일치          +2
```

최종 점수를 계산해:

```text
TOP 5
```

를 반환한다.

## 결과 예

```json
[
  {
    "performance_id": "P001",
    "score": 17,
    "matched_terms": [
      "반도체",
      "IP-R&D",
      "특허분석"
    ]
  }
]
```

## 요구사항

- deterministic
- explainable
- 외부 API 없음
- 고객 데이터 외부 전송 없음

## 테스트

- 동일 입력 동일 점수
- 명백한 관련 실적 상위
- 무관 실적 하위
- 키워드 중복 과대평가 방지
- 빈 실적 DB
- 동점 정렬 규칙
- TOP N

## 완료 조건

- [ ] 공고별 TOP N 추천
- [ ] 점수 이유 확인 가능
- [ ] 외부 API 없음
- [ ] 사용자가 가중치를 쉽게 수정 가능

---

# M15 — Personal Local Dashboard + Real-Use Gate

## 목표

내가 실제 업무에서 매일 사용할 수 있는 로컬 화면을 만든다.

이 단계가 개인용 v1의 마지막 구현 단계다.

## 화면 핵심

예:

```text
────────────────────────────────
특허법인 공고 모니터
최근 업데이트: 2026-10-30 07:15
────────────────────────────────

관련 공고 8건

[기관] KISTA
[공고] IP-R&D 협력기관 모집
[유형] 협력기관
[AI 판단] 참여 가능

[원문 보기]

유사실적
1. 반도체 IP-R&D 전략수립       18점
2. 반도체 특허동향 분석         15점
3. 첨단소재 특허분석             11점
────────────────────────────────
```

## 최소 기능

- feed 업데이트
- 신규/수정/전체 보기
- 기관 필터
- 카테고리 필터
- 텍스트 검색
- 공고 원문 열기
- Gemini 판정 이유 표시
- keywords 표시
- 유사실적 TOP N
- 매칭 점수/일치 키워드 표시
- 로컬 cache 상태 표시

## 구현 방식

개인용이므로 가장 단순한 방법을 선택한다.

예:

```text
로컬 웹앱
Python 내장 HTTP 서버 + 정적 HTML/JS
```

또는:

```text
간단한 데스크톱 UI
```

현재 코드와 유지보수 난이도를 기준으로 결정한다.

무거운 프레임워크 도입은 피한다.

## 실사용 Gate

구현 완료 후 최소 몇 주 실제 사용한다.

관찰할 것:

```text
공고 누락
불필요 공고 비율
Gemini 오판
수정 공고 판정 오류
실적 매칭 품질
필요한 실적이 TOP 5에 들어오는지
검색/필터 불편
페이지 로딩
실제 제안서 작성 시 도움 정도
```

## 실사용 로그

권장:

```text
docs/usage/ISSUES.md
docs/usage/IMPROVEMENTS.md
```

개인정보/민감 실적은 문서에 기록하지 않는다.

## 완료 조건

- [ ] GitHub feed를 실제 다운로드
- [ ] 로컬 실적 DB 연결
- [ ] 공고별 유사실적 표시
- [ ] 로컬 화면에서 매일 사용 가능
- [ ] 실사용 피드백을 기록할 구조 존재
- [ ] 판매용 기능 없이 개인용 v1 완료

---

# 4. 개인용 v1 이후

M15 이후에는 **바로 판매용 기능을 구현하지 않는다.**

실사용 후 다음 질문에 답할 수 있을 때만 v2를 설계한다.

```text
1. 실제로 매일 쓰는가?
2. 공고 누락이 충분히 적은가?
3. Gemini 선별 정확도가 실무적으로 쓸 만한가?
4. 유사실적 추천이 실제 제안서 작성에 도움이 되는가?
5. 어떤 사이트가 정말 중요한가?
6. 어떤 기능은 거의 사용하지 않는가?
7. 다른 특허법인이 돈을 낼 만한 핵심 가치는 무엇인가?
```

그 후 판매용 v2 후보:

```text
고객별 설치/설정
라이선스
고객별 사이트 추가
메일 알림
담당자 지정
법인 내부 협업
자동 업데이트
설치 패키지
고객별 실적 Import
유지보수 자동화
```

---

# 5. v2 개발 순서 요약

```text
M00  Repository Bootstrap                 ✅
M01  Site Inventory                       ✅
M02  Core Data Model                      ✅
M03  Normalizer / Stable Identity         ✅
M04  Scraper Framework                    ✅
M05  MVP Scrapers                         ✅
M06  Storage                              ✅
M07  NEW / UPDATED / EXISTING             ✅

M08  Central Gemini Relevance
M09  Public Notice Feed JSON
M10  Central End-to-End Pipeline
M11  GitHub Automation + JSON Distribution
M12  Local Feed Client
M13  Local Performance Database
M14  Local Performance Matcher
M15  Local Dashboard + Real-Use Gate
```

---

# 6. 현재 다음 작업

현재 다음 마일스톤은:

```text
M08 — 중앙 Gemini 공고 적합성 판정
```

이다.

M08 이후에는 판매를 위한 고객별 로직을 구현하지 않는다.

이번 프로젝트의 최종 목표는:

```text
GitHub 중앙 공고 feed
        ↓
내 PC
        ↓
내 실적 DB
        ↓
유사실적 추천
        ↓
내가 실제로 사용하는 로컬 화면
```

까지다.
