# M06 Result

## Status
PASS

검증일: 2026-10-30 (Asia/Seoul). M06 — Storage Layer만 수행했다.

## Implemented
- 표준 라이브러리 JsonStorage로 Notice 목록 및 scraper status snapshot load/save 구현.
- 기본 대상은 프로젝트의 data/notices.json 및 data/scraper_status.json이다.
  생성자에서 별도 data_dir를 지정할 수 있고 현재 작업 경로에 의존하지 않는다.
- 없는 파일만 []/{}로 읽는다. 최초 load/생성자 호출로 디렉터리/파일을 만들지 않는다.
- Notice.to_dict/Notice.from_dict 및 중첩 Gemini 모델 검증을 재사용한다.
- 저장 전 전체 schema/JSON/UTF-8 직렬화를 검증하고 같은 디렉터리의 임시 파일을 사용한다.
- write → flush → fsync → close → os.replace 순서의 단일 파일 atomic save를 구현했다.
- 손상/잘못된 schema/읽기·쓰기 실패를 구분하며 손상 파일을 자동 초기화하지 않는다.

## Files Added
- src/core/storage.py
- tests/test_storage.py
- docs/progress/M06_RESULT.md

## Files Modified
- docs/progress/CURRENT_STATE.md

## Tests
- command: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`
- result: **145 tests, OK**, 실패/오류 0, exit code 0.
- 신규 storage 16개 + 기존 129개 회귀 통과. 네트워크 호출 없음.
- 파일/디렉터리 없는 최초 상태, 빈 snapshot, 단일/복수 Notice 및 Gemini/null/enum 왕복 검증.
- SUCCESS/ERROR/WARNING status와 None/누락 선택 값/0건을 저장·복원했다.
- 입력 dict 키 순서가 달라도 동일 bytes, 동일 Notice 목록 반복 저장 시 동일 bytes,
  UTF-8 한글 및 LF/trailing newline을 확인했다.
- malformed/빈 JSON/비정상 UTF-8/중복 키/NaN·Infinity/잘못된 루트/필드/enum/type 오류를 검증했다.
- 기존 파일을 읽기 권한 오류 시 빈 저장소로 숨기지 않고 StorageIOError로 보고한다.
- 저장 도중 실패를 주입했다: 부분 write, fsync, os.replace.
  기존 notices/status bytes가 유지되고 실패한 첫 저장에는 파일이 게시되지 않음을 검증했다.
- 실제 os.replace 직전에 기존 파일이 완전하고, 같은 디렉터리의 임시 파일이 완전한 JSON인지 확인한 뒤
  실제 교체를 실행했다. 정상/오류 경로의 임시 파일 정리도 확인했다.
- 테스트는 workspace 내부 임시 디렉터리에서만 파일을 만들며 정리 대상 절대 경로를 먼저 검증한다.

## Manual Verification
- CURRENT_STATE/M05_RESULT/models.py 및 MILESTONES M06을 읽었다.
- 기본 경로는 실제 운영 data 경로로 확인하되 저장 테스트는 별도 임시 data_dir에서 수행했다.
  실제 data/notices.json 및 scraper_status.json을 빈 데이터로 생성/덮어쓰지 않았다.
- src.main, scraper, 모델/normalizer, fixture, 사이트 config, 의존성은 변경하지 않았다.
- 패키지 설치/Git/실제 네트워크/새 scraper/Gemini/diff/M07 이후 구현 없음.

## Acceptance Criteria
- [x] 파일 부재 시 빈 상태로 최초 실행 가능.
- [x] Notice 목록/여러 Notice 및 scraper status 왕복 통과.
- [x] 기존 Notice serialization 및 표준 라이브러리만 사용.
- [x] atomic save 및 실패 시 기존 정상 파일 보존 검증.
- [x] 결정적 JSON 포맷.
- [x] malformed JSON/schema 오류 처리 및 손상 파일 유지.
- [x] 전체 회귀 및 진행 문서 작성.

## Storage Contract
- notices.json 루트: Notice 객체 배열. 순서는 입력 목록 그대로 유지한다.
  각 객체는 M02 Notice의 전체 16개 필드, gemini는 전체 8개 필드를 가져야 한다.
  선택 필드도 JSON에 명시적으로 null로 저장하며 누락/미지 필드는 schema 오류다.
  모델 직접 생성 시의 기본값 허용과 달리, 저장 파일의 누락 필드를 임의 복원하지 않는다.
- scraper_status.json 루트: source_id → 상태 객체 mapping.
  source_id는 비어 있지 않은 문자열이다. record의 status는 필수 SUCCESS/ERROR/WARNING이다.
  선택 필드: last_attempt_at, last_success_at, notices_found, error_type, error_message.
  notices_found는 bool을 제외한 0 이상 int 또는 null, 나머지 선택 값은 빈 값이 아닌 문자열 또는 null이다.
  선택 필드 누락과 명시적 null을 모두 보존한다. 모르는 키/상태는 거부한다.
- status 판정/경고 감지/Registry 결과 연결은 구현하지 않았다. 현재 기능은 값의 검증과 저장뿐이다.
- 날짜/시각은 기존 계약처럼 문자열이며 저장 계층이 정규화/생성하지 않는다.

## Decisions
- API: JsonStorage(data_dir=None)의 load_notices/save_notices,
  load_scraper_status/save_scraper_status.
- 저장 형식: UTF-8, ensure_ascii=False, sort_keys=True, indent=2, LF와 마지막 newline,
  allow_nan=False. Notice 배열의 순서를 재배열하거나 중복을 병합하지 않는다.
- 오류: StorageFormatError(UTF-8/JSON/중복 키/상수), StorageSchemaError(데이터 계약),
  StorageIOError(파일 I/O). 모두 StorageError 하위 타입이고 원본 예외는 가능한 경우 cause로 보존한다.
- 저장 전 검증 실패 시 임시 파일을 만들지 않는다. 임시 파일은 대상과 동일 디렉터리에 생성해
  다른 파일시스템으로 이동하지 않는다. close 후 os.replace가 commit 지점이다.
- save는 호출자가 명시한 전체 snapshot 교체다. load 오류 후 자동으로 빈 snapshot을 save하는 로직은 없다.

## Known Issues
- M06 blocker 없음.
- 단일 writer 사용을 전제로 한다. 동시 writer 병합/locking 및 두 JSON 파일 간 transaction은 없다.
- 파일 fsync를 수행하지만 전원 장애에 대한 디렉터리 metadata 영속성까지 보장하지는 않는다.
- 강제 종료/정리 권한 오류가 있으면 임시 파일이 남을 수 있으나 load는 지정 JSON 파일만 읽는다.
  정리 실패가 원래 저장 오류를 덮어쓰거나 이미 성공한 commit을 실패로 보고하지 않도록 했다.
- 기존 scraper의 실제 네트워크/표본 범위 제한은 M05_RESULT를 따른다.

## Next Milestone Notes
- 다음 사용자 요청에서 M07 — NEW / UPDATED / EXISTING 판정만 진행한다.
  이번에는 diff/상태 전이/중복 처리/기존 Gemini 재사용을 구현하지 않았다.
- 기존 load_notices 결과를 입력으로 사용하고 저장은 명시적으로 호출한다.
  StorageError를 받으면 기존 데이터가 비었다고 간주해 덮어쓰지 않는다.
- scraper status는 source_id mapping schema를 따르며 실제 실행 상태 연결/관측 정책은 후속 범위다.
