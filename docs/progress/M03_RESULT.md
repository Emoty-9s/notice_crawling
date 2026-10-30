# M03 Result

## Status
PASS

검증일: 2026-10-30 (Asia/Seoul). M03 — Normalizer 및 Stable Identity만 수행했다.

## Implemented
- src/core/normalizer.py에 네트워크/시각/저장소에 의존하지 않는 정규화 함수를 구현했다.
- normalize_date: 점/하이픈/슬래시 및 한글 년월일 날짜와 한글 요일 접미사를 처리한다.
  명확한 전체 날짜만 실제 달력으로 검증해 YYYY-MM-DD로 반환한다.
- normalize_whitespace / normalize_institution: Unicode NFC 및 연속 Unicode 공백 정리.
  기관 별칭 병합, 법인 표기 삭제 등의 추측은 하지 않는다.
- normalize_url: 주변 공백/fragment 제거, scheme/host 소문자화, 기본 포트 제거,
  빈 루트 경로를 /로 통일. query 의미와 경로를 보존한다.
- clean_content_text: 추출된 일반 텍스트의 NFC/공백 정리.
- html_to_content_text: 명시적으로 HTML을 전달했을 때만 태그/주석 정리 및 entity 해석,
  head/script/style/nav/header/footer/template 제외, 문단·표 셀 사이 구분 유지.
- generate_notice_id / generate_content_hash는 M02 callable Protocol과 호환된다.
  Notice 모델 자체의 자동 생성 동작은 추가하지 않았다.

## Files Added
- src/core/normalizer.py
- tests/test_normalizer.py
- docs/progress/M03_RESULT.md

## Files Modified
- docs/progress/CURRENT_STATE.md

## Tests
- command: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`
- result: **40 tests, OK**, 실패/오류 0, exit code 0.
  M03 22개 + 기존 모델 17개 + M00 smoke 1개.
- 날짜 기본 4종을 포함해 6개 표현 및 윤년/잘못된 날짜/미완성·범위·문장 입력을 검증했다.
- 공백/NFC 동등성, 기관명 표기 보존, HTML 정리, 일반 텍스트 기호 보존,
  URL fragment/기본 포트/대소문자/원본 query 보존 및 잘못된 입력을 검증했다.
- ID 우선순위, source별/식별 방식별 분리, 제목 변경에 대한 상위 ID 안정성,
  fallback의 제목/URL 의존성, 공고별 ID 차이를 검증했다.
- 공백/NFC만 다른 본문의 동일 hash와 예산/날짜/문장부호 변경의 hash 차이를 검증했다.
- 서로 다른 PYTHONHASHSEED의 새 Python 프로세스에서 ID/hash가 같은지 검증했다.
- M02 Protocol 함수 할당 및 정규화 값으로 Notice 생성 → JSON round-trip 통과.

## Manual Verification
- 시작 전 M03 요구사항, CURRENT_STATE, M02_RESULT 및 models.py를 읽었다.
- SHA-256 표준 abc 벡터와 일치하는 본문 해시를 테스트로 확인했다.
- 기존 모델/실행 smoke도 통과했으며 모델 필드/기존 데이터 계약은 변경하지 않았다.
- 외부 패키지 추가/설치, Git, 네트워크, scraper/Gemini/M04 구현 없음.
- config/sites.yaml, 사이트 조사 문서, 원본 XLSB, 기존 코드/테스트를 수정하지 않았다.

## Acceptance Criteria
- [x] 요구된 날짜 변형 4개 이상 정규화.
- [x] 공백/기관명/URL/본문 정리 및 fragment 제거.
- [x] 같은 공고/같은 식별 근거 → 실행 간 같은 notice_id.
- [x] 다른 공고 및 source namespace → 다른 notice_id.
- [x] 공백/NFC만 다른 본문 → 같은 content_hash.
- [x] 실질 본문 변경 → 다른 content_hash.
- [x] 실제 unittest 결과 및 다음 단계 인계 문서 작성.

## Known Issues
- M03 blocker 없음.
- 날짜 범위/타임스탬프/연도 없는 날짜/알 수 없는 표현은 추측하지 않고 None이다.
  원문이 필요하면 호출자가 따로 보존한다. 이 함수는 관측 시각 변환용이 아니다.
- URL query 정렬/삭제, HTTP↔HTTPS 통합, 경로 대소문자/비루트 trailing slash 변경,
  인코딩 통합은 하지 않는다. 따라서 동일성을 입증하지 못한 URL은 별개로 남는다.
- 세션 URL/목록 URL이 안정적인 상세 URL인지 자동 판별하지 않는다. 호출자가 판단한다.
- fallback은 제목/URL이 바뀌면 ID도 바뀔 수 있다. 가능하면 상위 식별자를 지속적으로 공급한다.
  같은 공고라도 호출마다 선택하는 식별 단계가 달라지면 ID가 달라질 수 있다.
- HTMLParser는 브라우저가 아니다. 비정상 HTML/사이트별 본문 선택/텍스트에 섞인 메뉴 식별은
  향후 scraper 책임이며 일반 텍스트에서 메뉴를 추측해 삭제하지 않는다.
- whitespace 정리는 서식용 공백을 무시한다. 표 배치 등 서식 자체의 변화를 감지하지 않는다.
- KISTA/RIPC 자동수집 검증 대기는 M01에서 남긴 기존 제한이다.

## Decisions
- ID 우선순위: source_notice_id → notice_number → 안정적인 canonical 상세 URL →
  source_id + normalized title + canonical URL 조합.
- source_id는 모든 단계에 포함한다. 식별 종류와 버전도 JSON 배열에 포함해 구분자 충돌을 막고,
  UTF-8 SHA-256 전체 digest를 사용한다. ID 형식은 `notice:v1:<64자리 hex>`다.
- `url_is_stable=True`가 기본으로, 전달 URL을 상세 URL로 간주한다.
  안정적/고유하지 않은 URL은 False로 표시하고 fallback을 사용한다.
  URL이 비어도 제목이 있으면 fallback 가능하며 source_id/필요한 fallback 제목이 비면 ValueError다.
- source_notice_id/notice_number의 None/공백은 미제공으로 처리하며 문자열 "0"은 유효 ID다.
- content_hash는 일반 텍스트를 NFC/공백 정리한 뒤 UTF-8 SHA-256으로 계산한다.
  형식은 `content:v1:<64자리 hex>`. 제목/기관/시각 등 메타데이터는 포함하지 않는다.
- 빈 본문도 결정적인 hash를 갖는다. 본문 부재를 수집 성공으로 판단하는 로직은 없다.
- ID/hash v1 규칙을 향후 변경하면 기존 저장 데이터와의 migration을 별도로 결정해야 한다.

## Next Milestone Notes
- 다음 사용자 요청 시 M04 — Scraper Framework만 진행한다. 이번에 M04를 수행하지 않았다.
- 상대 URL은 호출자가 절대 URL로 해석한 뒤 normalize_url에 전달한다.
- scraper가 실제 상세 본문 fragment를 선택하고 html_to_content_text(HTML) 또는
  clean_content_text(일반 텍스트)를 적용한 뒤 generate_content_hash에 전달한다.
- 공통 ID 함수에 사이트 고유 ID/공고번호를 일관되게 전달하고, 불안정한 URL은 명시한다.
- 정규화된 값/생성 ID/hash로 Notice를 만들고 관측 시각은 호출자가 공급한다.
  상태 판정/저장/API 호출은 후속 마일스톤 범위다.
