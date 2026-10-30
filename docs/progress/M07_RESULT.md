# M07 Result

## Status
PASS

검증일: 2026-10-30 (Asia/Seoul). M07 — NEW / UPDATED / EXISTING 판정만 수행했다.

## Implemented
- src/core/diff.py에 순수 함수 compare_notice / compare_batch 구현.
- 기존 notice_id 없음 → NEW, 같은 ID의 의미 있는 변경 → UPDATED, 변경 없음 → EXISTING.
- 기존 first_seen_at/GeminiResult 보존, 관측 시각으로 last_seen_at 갱신.
- UPDATED 때만 updated_at 갱신하며 EXISTING은 기존 updated_at/내용 표현을 유지한다.
- 변경 field/before/after 및 중복 input index를 immutable 결과 객체로 노출한다.
- 현재 batch 동등 중복은 1건으로 축약, 충돌 중복 및 기존 저장 입력의 중복 ID는 명시적으로 거부한다.
- 입력 Notice 및 원본 목록은 수정하지 않는다. M02 frozen 모델 및 M03 정규화 함수를 재사용한다.

## Files Added
- src/core/diff.py
- tests/test_diff.py
- docs/progress/M07_RESULT.md

## Files Modified
- docs/progress/CURRENT_STATE.md

## Tests
- command: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`
- result: **166 tests, OK**, 실패/오류 0, exit code 0.
- 신규 diff 21개 + 기존 145개 회귀 통과. 네트워크 호출 없음.
- 신규/동일/본문·hash 변경/각 핵심 필드 변경/선택 값 제거/혼합 batch를 검증했다.
- 같은 batch의 신규 중복이 두 번째에 EXISTING으로 잘못 변하지 않는지 확인했다.
- 동등 중복의 축약/인덱스, 충돌 중복의 양방향 입력 순서 오류 및 기존 중복 ID 거부를 검증했다.
- 기존 Gemini 4개 status 모두에서 EXISTING/UPDATED 결과 보존을 검증했다.
- first_seen 유지/last_seen 갱신/updated_at 의미, 정규화 동등성, 입력 비변경,
  동일 입력·관측시각의 결과 결정성 및 변경 필드 고정 순서를 검증했다.
- 미관측 과거 공고를 삭제/상태 변경/last_seen 갱신하지 않음을 검증했다.

## Manual Verification
- CURRENT_STATE, M06_RESULT, models.py, storage.py, normalizer.py 및 MILESTONES M07을 읽었다.
- diff 모듈은 models/normalizer와 표준 라이브러리만 사용한다.
  storage를 import하거나 API/스크래핑/파일 읽기·저장/시계 조회를 하지 않는다.
- 관측시각은 호출자가 timezone 포함 ISO datetime 문자열로 전달한다.
- scraper/models/normalizer/storage/fixture/config/의존성 및 실제 data 파일은 변경하지 않았다.
- Git/패키지 설치/네트워크/M08 이후 구현 없음.

## Acceptance Criteria
- [x] NEW / UPDATED / EXISTING 상태 판정 deterministic.
- [x] first_seen 유지 및 last_seen 갱신.
- [x] 의미 있는 변경 시 updated_at 갱신, 변경 없으면 기존 값 유지.
- [x] 기존 Gemini 결과의 무의미한 초기화 없음.
- [x] 동일 실행 내 duplicate 처리 및 혼합 batch 지원.
- [x] 변경 필드와 이전/이후 값 추적 가능.
- [x] content_changed/변경 필드/보존한 analyzed_content_hash를 후속 정책에 전달 가능.
- [x] 실제 전체 unittest 및 인계 문서 작성.

## UPDATED Criteria
고정 비교 순서:

1. content_hash
2. content_text
3. title
4. institution
5. category
6. published_at
7. apply_start
8. apply_end
9. url

- content_hash는 공급된 값을 직접 비교한다. 본문도 공백/NFC 정리 후 비교하므로
  잘못 재사용된 hash와 실제 본문이 불일치해도 본문 변경을 놓치지 않는다.
  hash 계산/교정은 M03/호출자 책임이며 이 모듈은 값을 다시 만들지 않는다.
- 본문/제목/기관명/분류는 M03 NFC/공백 정리를 적용해 비교한다.
- 날짜는 M03이 해석하는 완전한 날짜면 ISO로 비교한다. 해석할 수 없는 문자열은
  정리한 원문을 비교하며 서로 다른 미상 문자열을 모두 None으로 만들지 않는다.
- URL은 M03 canonicalization(주변 공백/fragment 등) 기준이다.
- 선택 값의 None ↔ 문자열 변경은 UPDATED다.
- status/Gemini/first_seen_at/last_seen_at/updated_at은 변경 판정 필드가 아니다.
  같은 notice_id인데 source_id가 다르면 UPDATED로 합치지 않고 DiffInputError다.

## Result/API Contract
- compare_notice(collected, previous=None, *, observed_at) → NoticeDiff.
- compare_batch(collected, previous, *, observed_at) → BatchDiff.
  Iterable[Notice]를 받으며 전체 유효성이 확인되기 전 결과를 호출자에게 반환하지 않는다.
- NoticeDiff.notice는 새 frozen Notice, changes는 FieldChange(field/before/after) tuple이다.
  changed_fields는 고정 순서 tuple, content_changed는 본문/hash 변경 유무다.
  before/after는 실제 입력 값이며, 의미 비교에서 달라진 항목만 포함한다.
- NEW: first_seen/last_seen/updated 모두 observed_at. 입력 Gemini가 있으면 보존한다.
- UPDATED: 수집한 최신 내용 + 기존 first_seen/Gemini, last_seen/updated는 observed_at.
- EXISTING: 기존 내용 표현/Gemini/first_seen/updated 보존, last_seen/status만 갱신.
- NEW의 changes는 비어 있다(이전 값과의 차이가 없으므로). 상태로 신규를 구분한다.
- BatchDiff.results는 NoticeDiff tuple, notices는 관측한 고유 Notice의 list다.
  duplicates는 notice_id와 0-based input_indexes를 가진 DuplicateNotice tuple이다.
- 출력 순서는 수집 입력 ID의 첫 등장 순서다. 동일 ID의 현재 중복은 의미 있는 필드와
  source_id/Gemini payload가 같을 때만 축약하며 첫 번째 표현을 사용한다.
  관측시각/status 입력 차이만으로는 중복 충돌이 되지 않는다.
- 충돌 현재 중복/기존 중복 ID는 DiffConflictError다. ID/source 불일치·잘못된 입력/관측시각은
  DiffInputError다. 이 오류들은 임의 첫/마지막 값을 선택하여 숨기지 않는다.

## Known Issues
- M07 blocker 없음.
- observed_at은 호출자가 일관되고 올바른 관측시각을 공급해야 한다.
  과거 timestamps를 재해석/수정하거나 역전 시간을 자동 보정하지 않는다.
- BatchDiff는 이번에 실제 관측한 공고만 반환한다. 미관측 기존 공고를 포함하는 전체 저장 snapshot
  병합/실패 사이트 데이터 보존/저장은 M11 책임이다. notices만 전체 파일로 무조건 덮어쓰면 안 된다.
- 내용 충돌 중복은 batch 오류다. 어느 수집 결과가 신뢰할 만한지 선택하는 자동 정책은 없다.
- Gemini 결과를 보존하므로 UPDATED 결과의 analyzed_content_hash는 이전 본문 hash일 수 있다.
  이는 분석 이력이며 최신 분석 성공을 뜻하지 않는다. 호출/재시도/캐시 정책은 구현하지 않았다.
- content_hash 일치에도 본문 비교가 달라지면 content_changed=True다.
  후속 분석 정책은 이 변경 보고도 참고하고, 호출자는 수집 시 M03 hash를 올바르게 공급해야 한다.
- 기존 M05/M06의 운영 네트워크/표본/저장 동시성 제한은 그대로다.

## Decisions
- 순수 함수에 explicit observed_at을 받아 동일 입력의 결정성을 유지한다.
- 기존 Gemini는 상태와 관계없이 그대로 보존한다. 새 공고의 supplied Gemini도 임의 초기화하지 않는다.
- 동등 batch 중복을 모두 기존 저장 기록과 한 번만 비교하며 앞선 batch 결과를 '기존'으로 취급하지 않는다.
- 결과는 저장 모델 schema를 변경하지 않는 별도 audit 객체다. 자동 로그나 본문 출력은 하지 않는다.

## Next Milestone Notes
- 다음 사용자 요청에서 M08 — Gemini Relevance Policy만 진행한다. 이번에는 M08을 수행하지 않았다.
- M10은 변경 필드/content_changed 및 보존한 분석 hash를 사용해 재분석 정책을 정한다.
  이 모듈은 needs_analysis 정책이나 Gemini 호출을 구현하지 않는다.
- M11은 stored Notices와 관측 batch를 공급하고 미관측 기록을 보존하며 명시적으로 저장한다.
  StorageError/DiffInputError/DiffConflictError를 빈 정상 결과로 숨기지 않는다.
