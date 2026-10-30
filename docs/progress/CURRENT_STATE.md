# Current State

## Last Completed Milestone
M10 — Central End-to-End Pipeline. PASS (MILESTONES_V2.md 기준, 오프라인 E2E 검증).
M00~M09 PASS 유지(M05는 fixture 기반/오프라인 검증, M08 실제 API 미검증).
M08부터 V2의 번호/범위를 사용한다. 이전 RESULT의 후속 번호는 당시 계획의 이력이다.

## Current Milestone
M11 — GitHub Repository / Daily Automation / JSON 배포: **PARTIAL**.
workflow/보조 도구/문서/오프라인 검증 및 업로드 준비 완료. 대상은 Emoty-9s/notice_crawling(main/private)으로 확정했고 connector 관리자/push 권한을 확인했다.
실제 파일 업로드/Git remote 설정/Secret·Variable·Pages 설정/수동 실행/공개 URL 확인은 미완료다.

## Current Architecture
- src.main이 중앙 pipeline을 실행한다. 기본 config는 모두 비활성이므로 NO_ENABLED_SITES로 종료(code 2)한다.
- src/pipeline.py가 설정/저장 검증 → registry 수집·정규화 → diff → Gemini → 전체 병합 → 저장/feed/status를 연결한다.
- M02 Notice/GeminiResult 및 enum/JSON 계약, M03 정규화/안정적 ID/hash를 제공한다.
- M04 BaseScraper가 fetch/parse/normalize/run 및 HTTP timeout/retry/User-Agent를 제공한다.
- M05 사이트 adapter 5개가 실제 HTML fixture 기반으로 list[Notice]를 반환한다.
- 공통 HTML tree/StructureError 및 BoardScraper가 사이트 간 중복을 처리한다.
- Registry가 명시적 등록, 반환 계약 검증, 소스별 실패 격리 및 메모리 진단을 제공한다.
- M06 JsonStorage가 Notice/status JSON snapshot의 검증/load/atomic save를 제공한다.
- M07 compare_notice/compare_batch가 상태 판정, 변경 필드 및 중복 진단을 반환한다.
- M08 GeminiClient/RelevanceAnalyzer가 중앙 업계 참여 가능성을 구조화 판정하고 hash 캐시/실패 격리를 제공한다.
- 목표 흐름은 중앙 공통 JSON 배포 → 로컬 실적 매칭이다. 회사 실적/지원 의사는 중앙 판정에 포함하지 않는다.
- M09 build_feed/write_feed가 관련 공고를 공통 public JSON/metadata로 생성한다. 호출자가 시각/입력을 공급한다.
- M11 workflow가 daily/dispatch → 상태 artifact 복원 → 중앙 pipeline → 검증된 JSON pair Pages 배포를 구성한다.
- 실제 GitHub 연결/실행/Pages 배포는 아직 하지 않았다. V2 M12 이후 기능은 구현하지 않았다.

## Working Features
- 실제 목록 54개 파싱: KHIDI 14개, KISED/RDA/서울 R&D/KIPA 각 10개.
- 각 사이트 상세 표본 1개를 본문/메타데이터로 추출하고 Notice/JSON 생성.
- relative href 해석, 상세 origin/path/고유 ID 검증, 본문 밖 첨부/인접 글 제외.
- 빈 목록, 누락/변경된 구조의 명시적 실패 및 Registry 격리.
- JSON 파일 부재 시 빈 상태, Notice/status 왕복, schema 오류 보고 및 atomic save.
- NEW/UPDATED/EXISTING 판정, 기존 first_seen/Gemini 보존, 변경 필드 및 batch 중복 처리.
- Gemini 입력은 공고 8개 필드뿐이며 참여 유형/근거/키워드와 성공 분석 hash를 Notice에 저장할 수 있다.
- EXISTING 무호출, 같은 ID/hash 중복 호출 방지, 변경 hash 재분석 및 개별 분석 실패 격리.
- SUCCESS/relevant=true이며 완전한 현재 hash 분석 결과만 public feed에 포함한다.
- 공개 필드 15개, 최대 300자 본문 요약, 안정적 순서/JSON formatting 및 필터 후 metadata count를 제공한다.
- public/notices.json 및 public/metadata.json 생성 완료. 실제 분석 저장 데이터가 없어 초기 0건이다.
- 반복 실행에서 저장 5건 유지/EXISTING 무호출, 본문 변경만 UPDATED/재분석, 사이트·분석 부분 실패 격리 E2E 검증.
- 미관측/실패/비활성 사이트 기록을 보존해 저장/feed를 생성하고 scraper별 SUCCESS/ERROR/WARNING을 저장한다.
- M11 state 복원/보관, Secret scope, count/시각/snapshot 검증, Pages JSON allowlist와 안전한 진단을 추가했다.
- **244 unittest OK**: M11 15개 + 기존 229개. 별도 Node fake state selector 6개 PASS. 네트워크 의존 없음.
- 사용자 제공 실제 list.html/detail.html 10개를 수정 없이 사용.

## Business Context / M01 Coverage
- 사용자 조직은 특허법인. 수행/협력기관 모집 및 입찰 관점으로 대상 적합성을 판단한다.
- KIPA IP 디딤돌 수혜기업 전용 게시판은 범위 제외다.
- 원본 XLSB 49 URL → 47 수집원 coverage와 셀 참조/원본 해시 유지.
- M01 MVP는 총 7개다. M05에서 구현한 것은 아래 5개뿐이다.
  khidi_business, kised_bid_public, rda_bid, seoul_rnd_notice, kipa_bid.
- KISTA IP-R&D 협력기관 모집 / RIPC 협력기관 입찰은 미구현이며 기존 자동수집 검증 대기다.
- 기존 config/sites.yaml의 enabled=false는 유지한다. 테스트에서만 복사 config를 활성화한다.

## Known Broken / Pending
- M11 blocker: 저장소는 확정했으나 업로드/Actions/Pages 설정·실행은 미수행이다.
- connector에 Secret/Variable/Pages/최초 dispatch 기능이 없고 이전 UI는 현재 URL 검증 불가로 중단됐다. 사용자 지시에 따라 수동 설정 안내 후 중단한다.
- private repo Pages 지원 플랜 여부도 미확인이다. 지원하지 않더라도 public으로 전환하지 않는다.
- config/sites.yaml은 전부 false다. 구현된 수집원 하나 이상 활성화하고 GEMINI_API_KEY Secret/GEMINI_MODEL Variable을 설정해야 한다.
- M11은 수동 실행 성공/실제 두 JSON URL 확인 전까지 PARTIAL이다. 운영 순서는 docs/operations/GITHUB_PAGES.md 참고.
- state artifact는 90일 보존 요청이며 정책/삭제/장기 중단 시 복구가 필요하다. 유실/만료 시 자동 초기화하지 않는다.
- GitHub hosted Linux/공식 Actions/서버 workflow expression 검증은 아직 없다. JSON 문법 YAML 구조와 JS selector는 로컬 검증했다.
- M10 오프라인 구현 blocker 없음. 실제 실행은 활성 사이트와 GEMINI_API_KEY/GEMINI_MODEL 설정이 필요하다.
- 기본 src.main 실실행: NO_ENABLED_SITES, exit code 2, 외부 호출/운영 파일 저장 없음. 사용자 허용된 설정 오류 종료다.
- 손상된 Notice/status/중복 저장 ID는 수집 전에 중단한다. public 경로가 저장 파일과 겹치면 설정 오류다.
- 전체 파일 transaction은 없다. data 저장 후 feed 실패 시 data는 최신, public은 이전/부분 snapshot일 수 있고 오류를 전파한다.
- feed write 실패에도 scraper status 저장을 시도한다. 저장 실패는 성공으로 숨기거나 빈 데이터로 초기화하지 않는다.
- M09 blocker 없음. 현재 운영 public JSON은 기존 초기 빈 snapshot을 유지하며 E2E 산출물은 임시 저장소에서 검증했다.
- public 두 파일은 각각 atomic write다. 두 파일 전체 transaction은 아니므로 두 번째 파일 실패 시 시각/count 불일치가 가능하다.
- summary는 본문 일부 정리/최대 300자 발췌이며 생성형 요약이 아니다. 본문이 없으면 빈 문자열이다.
- M08 blocker 없음(mock 기반 완료). 실제 Gemini API/모델별 schema 지원·quota·응답 품질은 미검증이다.
- 실제 호출에는 GEMINI_API_KEY/GEMINI_MODEL을 프로세스 환경변수로 설정해야 한다. .env 자동 로딩/기본 모델 선택은 없다.
- FAILED/PENDING 재시도 스케줄은 없다. EXISTING은 분석 이력 부족/실패여도 호출하지 않는다.
- 기존 8필드 Gemini JSON도 읽지만 새 참여 유형/키워드는 null이다. 기존 결과를 자동 재분석하지 않는다.
- 캐시는 notice_id/content_hash 기준이다. 수집자는 M03 hash를 올바르게 공급해야 한다. 정책/모델 버전 변경 자동 무효화는 없다.
- M07 blocker 없음. 충돌 중복은 명시적 DiffConflictError이며 자동 승자 선택은 하지 않는다.
- batch 결과는 이번 관측 기록만 포함한다. M10이 미관측 저장 기록을 보존/병합한다. 자동 만료/삭제 정책은 없다.
- M06 blocker 없음. 단일 파일 atomic replace이며 동시 writer 병합/두 파일 transaction은 없다.
- 실제 운영 data 파일은 아직 생성하지 않았다. load는 없는 파일에 []/{}를 반환하고 save 시 파일을 만든다.
- M05 fixture blocker 없음. 10개 HTML 모두 UTF-8로 읽고 실제 DOM을 확인했다.
- 실제 네트워크 smoke는 이번 요청에 따라 미실행. 과거 로컬 DNS/브라우저 연결 실패 이력이 있다.
- 사이트별 상세 1개 표본만 검증했으며 운영 전체 유형/페이지에 대한 보증은 아니다.
- 현재 목록 페이지 수집만 구현했다. 자동 전 페이지 순회는 없다.
- 알려지지 않은 빈 목록 안내행/변형 구조는 []로 숨기지 않고 StructureError로 실패한다.
- KIPA 표본은 본문이 짧고 세부 내용은 첨부/나라장터에 있다. 외부/첨부 내용은 추론하거나 분석하지 않는다.
- 서울 R&D 편집기 HTML 일부 속성이 비정상이지만 fixture 본문은 정상 추출된다.
- 목록/상세 제목 불일치 시 실패하고 목록을 다시 수집해야 한다.
- KISTA 페이지 이동/RIPC 목록·페이지 요청, 기타 비선정 소스는 기존 M01 후속 제한이다.

## Important Files
- MILESTONES_V2.md: M08 이후 현재 범위/개발 순서. MILESTONES.md: M00~M07 이력/공통 계약.
- .github/workflows/central-notice-pages.yml: daily/dispatch/state/Pages workflow(JSON 문법 YAML 1.2).
- tools/actions_support.py / tests/test_actions_support.py: preflight/snapshot 검증/안전한 staging·진단 및 workflow 계약 테스트.
- docs/operations/GITHUB_PAGES.md / docs/progress/M11_RESULT.md: 실제 설정 절차·제한·blocker·검증 결과.
- src/main.py / src/pipeline.py: 중앙 명령/설정 검증 및 dependency injection 가능한 실행 함수.
- tests/test_pipeline.py / docs/progress/M10_RESULT.md: 실제 fixture E2E 및 실제 검증/운영 제한/인계.
- README.md: 현재 실행 전제/명령/종료 코드.
- src/renderer/feed.py / tests/test_feed.py: M09 공개 projection/JSON 작성 및 오프라인 테스트.
- public/notices.json / public/metadata.json: schema_version=1 초기 공통 feed 및 count/생성 시각.
- docs/progress/M09_RESULT.md: 공개 schema/실제 검증/원자적 저장 한계/후속 인계.
- config/relevance_policy.yaml: 중앙 판정 기준/예시/출력 schema(JSON 문법인 YAML 1.2).
- src/ai/gemini.py, src/ai/relevance.py: 표준 라이브러리 REST/응답 검증 및 캐시/실패 격리.
- tests/test_gemini.py: M08 mock 테스트, 저장 왕복 및 이전 JSON 호환성.
- docs/progress/M08_RESULT.md: M08 실제 검증/운영 제한/후속 인계.
- src/core/diff.py: compare_notice/compare_batch, NoticeDiff/FieldChange/BatchDiff 및 중복/입력 오류.
- tests/test_diff.py: 상태/변경/시각/Gemini 보존/중복/결정성 테스트.
- docs/progress/M07_RESULT.md: 실제 테스트/판정 기준/API/후속 인계.
- src/core/storage.py: JsonStorage, schema 검증 및 atomic JSON 저장/복원.
- tests/test_storage.py: 저장/복원/손상 입력 및 write·fsync·replace 실패 주입.
- docs/progress/M06_RESULT.md: M06 설계/실제 테스트/저장 schema/M07 인계.
- data/notices.json, data/scraper_status.json: 기본 저장 대상(첫 save 시 생성).
- src/core/models.py, src/core/normalizer.py: M02/M03 공통 계약.
- src/scrapers/base.py: M04 lifecycle/HTTP/오류 경계.
- src/scrapers/_html.py, _board.py: 공통 HTML 탐색 및 BoardScraper/Notice 변환.
- src/scrapers/{khidi_business,kised_bid_public,rda_bid,seoul_rnd_notice,kipa_bid}.py: M05 adapter.
- src/scrapers/registry.py: ScraperRegistry 및 build_mvp_registry.
- tests/fixtures/<source_id>/{list,detail}.html: 사용자 저장 실제 HTML, 원본 보존.
- tests/_site_cases.py, test_<source_id>.py, test_mvp_registry.py: 오프라인 M05 테스트.
- tools/fetch_fixtures.py / tests/test_fetch_fixtures.py: 독립 fixture 수집 도구 및 fake 테스트.
- docs/progress/M05_RESULT.md: 실제 DOM 근거/fixture hash/테스트/제한/인계.
- docs/progress/M05_FIXTURE_STATUS.md: 현재 확보 상태와 source URL.
- docs/progress/M00_RESULT.md~M04_RESULT.md: 이전 완료 이력.
- docs/site-audit/SITE_INVENTORY.md / config/sites.yaml: M01 조사·원본 추적 및 47개 수집원 전략.
- docs/site-audit/SOURCE_EXTRACT.json / 원본 XLSB: 원본 추출 근거.
- AUDIT_SUMMARY.json/build_inventory.py는 초기 스냅샷으로 최신 config 재생성에 사용하지 않는다.

## Test Commands
프로젝트 루트 PowerShell:

~~~powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
~~~

실제 실행 결과 244 tests OK, exit code 0. HTTP는 fake/Mock이며 원본 fixture는 바꾸지 않는다.
모듈 smoke는 --help 정상 종료를 검증하고, CLI 설정 오류/부분 실패/정상 코드는 별도 테스트한다.
`src.main` 기본 명령 실실행은 NO_ENABLED_SITES, native exit code 2를 확인했다.

## Environment / Secrets
- 기반 Python: C:\Users\이재혁\AppData\Local\Python\pythoncore-3.13-64\python.exe.
- 기본 python/py 대신 .venv\Scripts\python.exe 사용, Python 3.13.
- 외부 패키지 불필요. 패키지 설치/Git/실제 사이트·Gemini API 호출 없음. API 형식은 공식 문서로 확인했다.
- GEMINI_API_KEY/GEMINI_MODEL: 실제 호출에만 필요하며 unit test에는 불필요하다. .env.example에 이름만 제공한다.
- 키는 HTTP 헤더에만 전달하고 로그/오류/URL에는 넣지 않는다. 실제 secret 생성/출력 없음.
- 원본 XLSB SHA-256: 08bdd298d4219349cbf9b5a0ae0ef23dd39d93e8c865687f2f4a11e05e24ee3a.

## Next Recommended Action
실제 GitHub 저장소/Secret/Variable/사이트 활성화/Pages 설정 후 최초 수동 workflow 및 두 JSON URL을 확인해 M11을 완료한다.
그 후 사용자 요청 시 V2 M12를 진행한다. 이번에는 M12 이후를 구현하지 않았다.
M05 API 사용: build_mvp_registry(site_configs, transport_factory=..., clock=...) → registry.run().
site_configs는 mapping 리스트이고 enabled 설정을 존중한다. 등록만으로 HTTP를 호출하지 않는다.
M07 비교 함수는 순수 함수이며 저장은 호출하지 않는다. M10이 M08 분석 및 저장/feed 호출을 명시적으로 수행한다.
StorageError/DiffInputError/DiffConflictError를 빈 정상 결과로 숨기지 않는다.

## M06 Storage Contract / Handoff

- `from src.core.storage import JsonStorage, StorageError`.
- JsonStorage(data_dir=None)는 프로젝트 data에 notices.json 및 scraper_status.json 경로를 둔다.
  load_notices/save_notices, load_scraper_status/save_scraper_status를 제공한다.
- 없는 파일만 []/{}다. 손상 UTF-8/JSON/중복 키/비표준 상수는 StorageFormatError,
  계약 위반은 StorageSchemaError, 파일 I/O 실패는 StorageIOError다. 자동 초기화/복구/저장은 하지 않는다.
- Notice 저장 파일은 모델의 전체 필드(선택 값 null 포함)를 요구하고 모델 serialization을 재사용한다.
- scraper status는 source_id → record mapping이다. status 필수 SUCCESS/ERROR/WARNING;
  선택 last_attempt_at/last_success_at/notices_found/error_type/error_message를 보존한다.
  notices_found는 0 이상 int(bool 제외) 또는 None, 선택 텍스트는 비어 있지 않은 문자열 또는 None이다.
  M10이 registry 결과를 이 schema로 저장한다. 분석 성공 여부와 수집 상태는 구분한다.
- 저장은 전체 검증/UTF-8 직렬화 → 같은 디렉터리 임시 파일 → write/flush/fsync/close → os.replace다.
  실패 전 기존 파일은 유지한다. 원래 파일을 먼저 열어 truncate하지 않는다.
- 포맷은 UTF-8 한글, 객체 키 정렬, 2칸 indent, LF/trailing newline이다. Notice 목록 순서는 보존한다.
- 단일 writer 전제이며 두 파일 동시 transaction/동시 실행 병합/전원 장애 영속성 보장은 없다.
  강제 종료나 정리 권한 오류로 남은 임시 파일은 load 대상이 아니다.
- 검증: M06 16개 + 기존 129개 = 총 145 tests OK. 실제 data JSON/원본 fixture 및 다른 단계 코드는 변경하지 않았다.

## M07 Diff Contract / Handoff

- `compare_notice(collected, previous=None, observed_at=...)` → NoticeDiff.
- `compare_batch(collected, previous, observed_at=...)` → BatchDiff; 입력은 Notice iterable, 관측 시각은 timezone 포함 ISO 문자열이다.
- ID 없음 NEW, 같은 ID의 content_hash/정리한 content_text/title/institution/category/published_at/apply_start/apply_end/url 변경은 UPDATED, 아니면 EXISTING.
- 의미 비교는 M03 공백/NFC/완전한 날짜/URL 정규화를 사용한다. 미해석 날짜 문자열은 원문 의미를 구별한다.
- 신규 시각은 observed_at으로 설정한다. 기존 first_seen/Gemini는 보존하며 last_seen은 갱신한다.
  UPDATED의 updated_at만 갱신하고 EXISTING은 기존 내용 표현과 updated_at을 유지한다.
- 결과의 changes는 field/before/after tuple, changed_fields는 고정 순서이며 content_changed는 본문/hash 변경 유무다.
  Gemini 재분석 정책/호출은 없고 기존 analyzed_content_hash가 보존되어 후속 판단이 가능하다.
- BatchDiff.notices는 이번 관측 ID만 담는 list다. 결과를 전체 저장소라고 간주하지 않는다. 미관측 기록은 V2 M10에서 보존/병합한다.
- 동등 현재 중복은 첫 등장 1건만 비교하고 input_indexes를 보고한다. 동일 ID의 내용/source/Gemini 충돌은 DiffConflictError다.
  기존 저장 입력의 중복 ID도 임의 덮어쓰기 없이 오류다. 서로 다른 notice/source를 단일 비교하면 DiffInputError다.
- 입력 객체 비변경, 동일 입력/observed_at 결과 결정성 검증. 관측 시각 역전 자동 보정은 하지 않는다.
- M07 신규 21개 + 기존 145개 = 166 tests OK. scraper/models/normalizer/storage/config/fixture/실제 data 및 의존성 변경 없음.

## M08 Gemini Contract / Handoff

- `RelevanceAnalyzer(GeminiClient()).analyze(notice)` → 새 Notice; `analyze_batch(notices)` → list[Notice].
  중앙 실행에서 analyzer 하나를 공유한다. 생성/import만으로 HTTP 호출/저장은 하지 않는다.
- 성공은 relevant/category/participation_type/reason/keywords 및 analyzed_at/analyzed_content_hash를 gemini에 기록한다.
  keywords는 모델에서 immutable tuple, JSON에서는 array다. 기존 score는 호환성용이며 M08은 null로 둔다.
- 완전한 SUCCESS + 현재 hash 일치 → 재사용. NEW/UPDATED 분석, hash 변경 재분석, EXISTING 무호출.
  같은 실행에서 실패 포함 동일 ID/hash는 1회만 시도한다. 성공 결과는 Notice JSON으로 다음 실행에 인계 가능하다.
- timeout/네트워크/429/5xx/설정 누락은 PENDING, malformed JSON/schema/기타 API 오류는 FAILED다.
  원문 오류/키 대신 고정 진단 코드만 기록하고 다음 공고는 계속 처리한다.
- 재분석 실패 시 이전 판단/hash/시각을 보존하되 SUCCESS로 표시하지 않는다.
  analyzed_content_hash는 마지막 성공 hash이며 실패한 본문의 분석 완료를 뜻하지 않는다.
- storage는 이전 8필드/현재 10필드 Gemini 객체를 허용한다. 부분 추가 schema는 거부한다.
  load만으로 이전 파일을 다시 쓰지 않는다. 실제 data JSON은 생성/수정하지 않았다.
- M09 인계: 오래된/불완전한 분석 결과와 현재 본문 분석 성공을 구분해야 한다.
  M09에서 이 조건을 확인하여 feed를 생성하고 M10이 연결한다. 로컬 매칭/실적 DB는 미구현이다.

## M09 Public Feed Contract / Handoff

- `build_feed(notices, *, generated_at)` → dict. 순수 projection이며 Notice iterable을 받는다.
- `write_feed(notices, *, generated_at, output_dir=None)` → (notices_path, metadata_path).
  기본 위치는 작업 경로와 무관한 프로젝트 public 디렉터리다. import만으로 파일을 쓰지 않는다.
- generated_at은 호출자가 timezone 포함 ISO 문자열로 주입하며 UTC Z 표기로 정규화한다. 내부 시계 조회는 없다.
- 포함: gemini.status=SUCCESS, relevant=true, analyzed_content_hash=content_hash 및 M08 출력 필드 완비.
  FAILED/PENDING/NOT_ANALYZED/irrelevant/미상 판단/오래된·불완전한 SUCCESS는 제외한다.
- Notice status(NEW/UPDATED/EXISTING)와 관계없이 유효한 관련 공고를 포함한다. AI 재호출은 없다.
- 루트는 schema_version=1/generated_at/notices. 공고는 명시적 15필드 allowlist다.
  category는 Gemini 분류, participation_type/keywords/relevance_reason은 Gemini 결과를 반영한다.
  dates 미상은 null, keywords는 array다. content_text/Gemini 원본/해시/score는 배포하지 않는다.
- 요약은 M03 텍스트 정리 후 최대 300자이며 긴 본문은 말줄임표로 끝난다. 짧은 본문은 정리한 발췌 그대로다.
- 공고 정렬은 (source_id, notice_id), 객체 키 정렬/2칸 indent/UTF-8/LF/trailing newline이다.
  같은 입력/시각은 동일 JSON bytes, 시각만 바뀌면 notices data는 동일하다.
- 동일 ID의 같은 공개 record는 축약한다. 공개 내용이 충돌하면 FeedInputError이며 임의 승자를 선택하지 않는다.
- metadata는 같은 snapshot의 schema_version/generated_at/필터·중복 제거 후 notice_count다.
- M06 내부 atomic JSON primitive를 재사용한다. 입력 오류/첫 write 실패 시 기존 두 파일 보존,
  두 번째 write 실패 시 첫 파일만 갱신될 수 있다. 파일 오류는 StorageError로 호출자에게 전파한다.
- 생성물 검증: generated_at=2026-10-30T07:20:38.339587Z, 공고 0건, 두 파일 독립 JSON parsing 성공.
- V2 M10에서 저장된 전체 snapshot을 명시적으로 공급하고 오류/성공 여부를 관리한다.
  M10에서 src.main/registry/AI/storage/feed를 연결했다. 배포, 로컬 매칭은 미구현이다.

## M10 Pipeline Contract / Handoff

- `run_pipeline(client=..., config_path=..., storage=..., public_dir=..., clock=..., transport_factory=...)` → PipelineResult.
  기본 config/data/public은 프로젝트 경로다. 테스트에서는 실제 HTML용 transport, fake Gemini, 임시 경로, 고정 clock을 주입한다.
- config/sites.yaml은 JSON 문법 YAML이며 중복/잘못된 enabled/미구현 활성 수집원/누락된 MVP 설정을 거부한다.
  run_pipeline 함수는 전부 비활성인 입력도 처리할 수 있지만 실제 CLI는 실수로 빈 실행하지 않도록 오류 종료한다.
- 시계는 실행당 1회 조회한다. registry 내부 normalize를 재사용하고 ID/hash를 orchestration에서 다시 생성하지 않는다.
- 손상 저장소를 먼저 검증한 후 수집한다. M07 current batch + 기존 전체 snapshot을 ID로 병합하고 (source_id, notice_id)로 정렬한다.
- 관측 기록만 diff/Gemini 대상이다. EXISTING은 API 무호출, 미관측 기록은 status/시각/분석 이력까지 그대로 유지한다.
- scraper success는 SUCCESS/count/관측 시각, 실패는 ERROR/안전한 단계 진단/이전 last_success 유지,
  비활성은 WARNING/DISABLED/이전 시각 유지다. 미등록 수집원의 기존 status도 보존한다.
- PipelineResult.notices는 전체 snapshot, observed는 관측 결과, scraper_failures/analysis_failures는 이번 오류 ID,
  skipped는 비활성 등록 수집원, feed_count는 실제 공개 대상 수다. 실패 건이 있으면 degraded다.
- CLI exit 0=완료, 1=부분 실패 후 데이터/feed/status 생성, 2=설정/저장/diff/feed/예상 밖 오류.
  키/원문 exception을 출력하지 않는다. API 키/모델 이름을 출력하지 않으며 .env 자동 로딩도 없다.
- E2E 결과: 처음 5 NEW/5 분석/5 feed → 동일 재실행 5 EXISTING/추가 분석 0 → 본문 1개 변경 시 1 UPDATED/추가 분석 1.
- GitHub 연결/Actions/Pages/배포 URL/로컬 클라이언트/실적 DB/매칭은 구현하지 않았다.
  위 항목은 M10 시점의 이력이다. M11에서 Actions/Pages workflow를 추가했으며 실제 연결/URL 확인은 아직 남아 있다.

## M11 Workflow Contract / Handoff

- daily 22:17 UTC(07:17 KST), workflow_dispatch. 기본 브랜치만 허용하며 단일 concurrency group/cancel=false다.
- checkout → Python 3.13(stdlib only) → unittest → 설정 검사 → state 복원/검증 → M10 pipeline → feed snapshot 검증/staging → state/Pages artifact → deploy.
- GEMINI_API_KEY는 repository Actions Secret, GEMINI_MODEL은 Variable이다. 값 출력/파일 저장 없이 두 필요한 step에만 주입한다.
- central-state-v1 artifact에 Notice/status를 90일 보관 요청하고 다음 실행에 복원한다. 첫 빈 시작은 수동 bootstrap_state=true만 허용한다.
- Pages에는 .run/pages/notices.json 및 metadata.json만 포함한다. raw data/진단/secret은 배포하지 않는다.
- exit 1=PARTIAL warning 후 검증된 결과 배포, exit 2 이상/검증 실패는 deploy 중단. 예전 Pages를 지우거나 빈 값으로 대체하지 않는다.
- preflight/state/pipeline/staging/deploy step과 Summary, 안전한 진단 artifact(14일)로 원인을 확인한다.
- build 권한 contents read/actions read, deploy만 pages write/id-token write. 추가 PAT/로컬 credential은 필요 없다.
- src/main/pipeline/core/AI/scraper/feed 및 운영 config/data/public은 변경하지 않았다. Git 명령/실제 저장소 쓰기/실제 Secret 입력도 없다.
- 실제 GitHub 실행/수동 성공/배포 URL 확인이 남아 있으므로 M11은 PARTIAL이며 M10이 마지막 완료 milestone이다.

## M11 Confirmed Repository / Manual Handoff

- Repository: https://github.com/Emoty-9s/notice_crawling, ID 1439083905, main, private, 관리자/push 권한 확인.
- 원격 파일 반영은 아직 없다. .run/M11_UPLOAD.zip 및 .run/M11_PUSH_MANIFEST.json으로 업로드할 파일을 준비했다.
  .venv/.git/.env/credential/원본 XLSB는 제외한다. 실제 key를 읽어 출력하거나 패키지에 넣지 않았다.
- 수동 순서: 압축 해제 파일을 main에 반영 → GEMINI_API_KEY Secret → GEMINI_MODEL Variable → 구현 source 활성화
  → private 지원 플랜/Pages Actions source/권한 확인 → 최초 bootstrap_state=true dispatch → build/deploy 및 Gemini SUCCESS 확인
  → 실제 page_url의 notices.json/metadata.json 공개 접근 확인.
- 정확한 repository별 링크/주의사항은 docs/progress/M11_RESULT.md의 Confirmed Repository / Push Preparation / Manual Stop에 있다.
- private 유지, M12 미착수. 실제 로그/URL 증거가 없으므로 PASS로 변경하지 않는다.
