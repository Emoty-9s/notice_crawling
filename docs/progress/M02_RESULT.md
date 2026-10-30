# M02 Result

## Status
PASS

검증일: 2026-10-30 (Asia/Seoul). M02 — Core Data Model만 수행했다.

## Implemented
- MILESTONES.md 3절 계약의 Notice 16개 필드와 GeminiResult 8개 필드를 정의했다.
- NoticeStatus: NEW / UPDATED / EXISTING.
- GeminiStatus: NOT_ANALYZED / SUCCESS / FAILED / PENDING.
- 두 모델에 to_dict / from_dict / to_json / from_json을 제공한다.
- 문자열 상태 입력은 enum으로 변환하며, 잘못된 상태는 ValueError로 거부한다.
- 필드 타입, 중첩 모델, JSON 객체 형태를 검증한다. 필수 필드 누락/알 수 없는 키는 TypeError다.
- NoticeIdGenerator / ContentHashGenerator는 callable Protocol 인터페이스만 정의했다.
  실제 ID 생성, hash 계산, 정규화는 구현하지 않았다.

## Files Added
- src/core/models.py
- tests/test_models.py
- docs/progress/M02_RESULT.md

## Files Modified
- src/core/__init__.py: 현재 모델 패키지 설명으로 변경.
- docs/progress/CURRENT_STATE.md

## Tests
- command: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`
- result: **18 tests, OK** (모델 17개 + 기존 M00 smoke 1개), 실패/오류 0.
- 정상 생성/정확한 계약 키, optional null, 기본값 및 전체 값 JSON round-trip,
  모든 상태 문자열/enum, 중첩 Gemini 복원, 잘못된 상태/타입/JSON 객체,
  필수 필드 누락/알 수 없는 키, False/0 유지, NaN/Infinity 거부를 검증했다.
- JSON 복원이 입력 dict를 변경하지 않으며, 모델 상태를 검증 없이 수정할 수 없는지 확인했다.
- 공급된 ID/hash/날짜/본문을 자동 정규화하지 않는 경계도 검증했다.

## Manual Verification
- 테스트가 `src.core.models`에서 모델을 직접 import하여 생성/직렬화/복원했다.
- M01 config의 수집원 47개, MVP 7개(경로 검증 완료 5개/대기 2개), enabled=false를 읽고 확인했다.
  config와 M01 조사 산출물은 변경하지 않았다.
- 외부 패키지 의존성 추가, 설치, 네트워크 호출, Git 명령 실행 없음.
- scraper/Gemini API/사이트별 로직/M03 계산 구현 없음. 기존 src.main 동작 유지.

## Acceptance Criteria
- [x] 공통 Notice 및 Gemini 계약이 코드로 고정됨.
- [x] 필수/선택 필드, 날짜 표현 규칙 및 상태 enum 정의.
- [x] JSON serialization/deserialization 테스트 통과.
- [x] 이후 scraper에서 import 가능한 모델 제공.
- [x] ID/hash 생성 인터페이스만 준비하고 구현은 M03으로 남김.
- [x] unittest 실제 결과 및 인계 문서 기록.

## Known Issues
- M02 blocker 없음.
- 날짜 문자열의 ISO 변환/유효성 정규화, URL canonicalization, 본문 정리,
  ID/hash 생성은 아직 없다. M03에서 수행한다.
- Gemini SUCCESS의 필수 출력 조합, score 범위 및 정책 검증은 M08/M09 범위다.
  현재 공통 계약대로 score는 유한한 int/float 또는 None이다(bool 제외).
- KISTA 페이지 이동과 RIPC 입찰 목록/페이지 요청 검증 대기는 M01의 기존 제한으로 유지한다.

## Decisions
- 표준 라이브러리 dataclass(frozen=True, kw_only=True), StrEnum, json, Protocol 사용.
  모델 변경은 dataclasses.replace 또는 새 인스턴스로 수행하며 자동 상태 전환은 없다.
- 필수 문자열: notice_id/source_id/institution/title/url/content_text/content_hash 및
  first_seen_at/last_seen_at/updated_at. 호출자가 명시적으로 제공한다.
  content_text는 웹 본문이 없으면 빈 문자열을 허용한다.
- 선택 문자열은 category/published_at/apply_start/apply_end 및 Gemini 설명/범주/분석시각/hash다.
  생략 시 None → JSON null. 빈 문자열/공백만 있는 선택 문자열은 ValueError로 거부한다.
- status 기본값 NEW, gemini 기본값은 독립적인 GeminiResult(NOT_ANALYZED)다.
  Gemini 선택 값은 모두 None으로 초기화하며 자동 분석/판정은 하지 않는다.
- 날짜 표현: 가능하면 YYYY-MM-DD, 시각은 offset 포함 ISO 문자열(UTC는 Z 가능).
  현재는 문자열을 보존하며 날짜 파싱/정규화 또는 현재 시각 생성은 하지 않는다.
- from_dict는 중첩 gemini 객체를 GeminiResult로 복원한다. gemini null은 계약상 허용하지 않는다.
  직접 생성할 때는 GeminiResult 인스턴스를 전달한다. 미지의 필드는 조용히 버리지 않는다.

## Next Milestone Notes
- 다음 사용자 요청 시 M03 — Normalizer 및 Stable Identity만 진행한다.
- NoticeIdGenerator 입력은 source_id/title/url 및 선택적 source_notice_id/notice_number,
  출력은 str이다. ContentHashGenerator는 content_text를 받아 str을 반환하는 계약이다.
- 생성 함수/normalizer에서 정규화한 값과 안정적인 ID/hash를 Notice에 공급한다.
  모델에서 ID/hash/시각을 암묵적으로 만들지 않는다.
- 날짜 변형 및 동일 공고/본문의 안정성 테스트를 M03에서 추가한다.
- 사이트별 수집/API 호출/저장/diff 등 후속 마일스톤은 이번에 수행하지 않았다.
