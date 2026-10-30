# M04 Result

## Status
PASS

검증일: 2026-10-30 (Asia/Seoul). M04 — Scraper Framework만 수행했다.

## Implemented
- BaseScraper[Item, Parsed] 추상 기반 클래스와 ScraperRegistry를 구현했다.
- 공통 흐름: fetch_list → parse_list → 항목별 fetch_detail → parse_detail → normalize.
  run의 성공 결과는 list[Notice]이며 Notice.source_id도 현재 수집원과 일치해야 한다.
- 사이트 config는 생성 시 deepcopy하며 최상위 mapping은 읽기 전용이다.
  source_id, enabled, list_url 및 나머지 사이트별 설정을 참조할 수 있다.
- HttpSettings / HttpTransport / UrllibTransport로 timeout·User-Agent·retry를 공통화했다.
  transport와 sleep을 주입할 수 있어 테스트에 네트워크/실제 대기가 필요 없다.
- ScraperError에 source_id/stage/error_type 및 원본 예외 cause를 보존한다.
- Registry는 등록 순서대로 실행하고 소스 하나의 예외를 기록한 뒤 다음 소스를 계속 실행한다.
  결과 계약을 다시 검증하므로 하위 클래스가 run을 재정의해도 잘못된 결과를 게시하지 않는다.
- logging 모듈로 성공/개수, 실패 단계/오류 종류, 재시도, 비활성 건너뛰기를 기록한다.
  응답 본문/전체 config/요청 URL/원본 예외 메시지는 기본 로그에 넣지 않는다.

## Files Added
- src/scrapers/base.py
- src/scrapers/registry.py
- tests/test_scraper_base.py
- docs/progress/M04_RESULT.md

## Files Modified
- docs/progress/CURRENT_STATE.md

## Tests
- command: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`
- result: **61 tests, OK**, 실패/오류 0, exit code 0.
  M04 21개 + M03 22개 + 모델 17개 + M00 smoke 1개.
- fake scraper로 목록/상세 응답 → M03 정규화/ID/hash → M02 Notice → JSON 왕복을 검증했다.
- 빈 목록, 비활성 소스, 목록/상세 parsing 실패, 전체 단계별 오류 정보,
  잘못된 parse_list/normalize/run 반환값 및 source 불일치를 검증했다.
- timeout/UA 전달, 일시 네트워크 오류 재시도, retry 소진/0회, 지수 backoff 상한,
  HTTP 상태별 retry 정책 및 HTTP 응답 자원 종료를 검증했다.
- Registry의 실패 격리, 중간 상세 실패 시 부분 결과 미게시, 등록 순서/중복 거부,
  매 실행 상태 초기화 및 KeyboardInterrupt 전파를 검증했다.
- 모든 HTTP는 Mock transport 또는 패치된 urlopen을 사용했다. 실제 네트워크/재시도 대기 없음.

## Manual Verification
- 시작 전 CURRENT_STATE, M03_RESULT, models.py, normalizer.py 및 MILESTONES M04를 읽었다.
- BaseScraper는 구체 사이트 구현이 아니며 테스트용 FakeScraper는 tests에만 존재한다.
- 기존 M00~M03 테스트도 모두 통과했다. 기존 모델/ID/hash 규칙 및 src.main은 변경하지 않았다.
- M01 config의 enabled 설정은 변경하지 않았다. 등록/생성만으로 네트워크 호출하지 않는다.
- requests/BeautifulSoup/Playwright 및 다른 외부 패키지 추가/설치 없음.
- Git, Gemini/Storage 구현, 실제 사이트 수집 및 M05 이후 작업 없음.

## Acceptance Criteria
- [x] 공통 fetch_list/parse_list/fetch_detail/parse_detail/normalize/run 제공.
- [x] 사이트 config 및 HTTP timeout/retry/User-Agent 설정 가능.
- [x] Mock scraper end-to-end run 성공, 빈 목록 처리.
- [x] parsing 실패를 소스/단계별 오류로 보고.
- [x] 한 scraper 실패에도 다른 scraper 계속 실행.
- [x] 성공 반환값이 list[Notice]이며 잘못된 결과 차단.
- [x] 네트워크 없는 unittest 실제 통과 및 인계 문서 작성.

## Known Issues
- M04 blocker 없음.
- 실제 사이트 scraper/실제 네트워크 동작은 검증하지 않았다. 사이트별 parsing,
  페이지 이동/응답 인코딩 및 실제 HTTP 안정성 검증은 M05에서 수행한다.
- 기본 HTTP 어댑터는 GET/text 전용이다. POST/JSON/session/browser가 필요한 사이트는
  검증 근거에 따라 fetch 메서드/transport를 확장해야 한다. 접근통제는 우회하지 않는다.
- timeout은 urllib socket 작업에 적용되며 전체 scraper 실행 시간의 강제 deadline은 아니다.
  retry는 Retry-After 해석을 포함하지 않는 기본 bounded backoff다.
- 항목 하나라도 실패하면 그 소스는 전체 실패하며 부분 성공 결과를 반환하지 않는다.
  다른 소스의 성공 결과는 유지한다. 항목별 부분 성공 정책은 이번 범위가 아니다.
- 사이트 config 파일 loader/자동 등록, 저장/diff/지속 상태 보고는 구현하지 않았다.
  Registry의 results/errors/skipped는 실행별 메모리 진단이며 M12 상태 저장 구현이 아니다.
- KISTA 페이지 이동/RIPC 입찰 목록·페이지 요청 검증 대기는 기존 M01 제한으로 유지한다.

## Decisions
- fetch_list 기본 구현은 config.list_url을 request_text로 GET한다.
  나머지 parse_list/fetch_detail/parse_detail/normalize는 하위 클래스 구현 지점이다.
  네트워크 fetch에서는 request_text를 사용해야 공통 HTTP 정책이 적용된다.
- normalize는 M02 Notice를 반환하며 M03 함수를 재사용한다. 관측 시각 공급은 하위 클래스/호출자 책임이다.
- HTTP 설정: `http` config 또는 명시적 HttpSettings 인자.
  timeout_seconds=15, max_retries=2(최초 요청 외 추가 횟수), backoff_seconds=0.5,
  user_agent=NoticeMonitor/0.1이 기본이다. 명시적 HttpSettings가 config.http보다 우선한다.
- timeout/URLError/ConnectionError 및 429/500/502/503/504만 재시도한다.
  대기는 backoff_seconds × 2^attempt, 회당 최대 30초다.
  400/401/403/404, parsing/정규화/반환 타입 오류는 재시도하지 않는다.
- enabled가 없거나 false면 비활성이다. BaseScraper.run과 Registry 모두 비활성 소스를 호출하지 않는다.
  Registry는 실제 실행한 성공(빈 목록 포함), 실패, 비활성을 각각 results/errors/skipped로 구분한다.
- 등록은 BaseScraper 인스턴스를 명시적으로 register하며 source_id 중복은 ValueError다.
  구성/등록 오류는 실행 전에 수정해야 하며 실행 중 소스 예외와 구분한다.
- Exception을 격리하지만 KeyboardInterrupt/SystemExit 등 BaseException은 전파한다.

## Next Milestone Notes
- 다음 사용자 요청 시 M05 — MVP Scrapers를 진행한다. 이번에 M05를 수행하지 않았다.
- 각 scraper를 BaseScraper 하위 클래스로 정의하고 해당 site config를 전달한다.
  fetch_list(필요 시 override)/fetch_detail은 공통 request_text 또는 검증된 별도 transport를 사용한다.
- parse_list는 list[Item], parse_detail은 Parsed, normalize는 Notice를 반환한다.
  빈 정상 목록은 []이며 파싱 불가/예상 selector 부재를 빈 목록으로 숨기지 않는다.
- Registry에 인스턴스를 등록한 뒤 run() 결과를 사용하고 errors/skipped도 확인한다.
  현재 sites.yaml의 enabled=false를 이번에 일괄 활성화하지 않았다.
- M01 MVP는 7개(경로 검증 완료 5개 + KISTA/RIPC 검증 대기 2개)다.
  M05 기본 5개 구현 범위와 추가 두 소스의 도입 시점은 후속 사용자 지시를 따른다.
