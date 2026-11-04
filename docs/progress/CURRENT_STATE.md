# Current State

Latest central eligibility resume (2026-11-04): 중앙 관측 history는 만료 후에도 삭제하지 않는다.
공개 feed v2는 현재 `patent-firm-participation-v2`/hash SUCCESS·참여 가능·유효 공고만 projection한다.
NEW는 현재 중앙 run의 신규 발견이며 local seen과 독립적이다. 기본 분석 예산 60회,
실 provider 간격 6초, 429 이후 run 호출 중단. 7개 operational source는 최대 3페이지,
KISTA/RIPC POST/AJAX 유지, checked-in enabled 설정 유지.
재개 최종 검증: 전체 588 tests PASS (144.260초), 공식 7개 source 각 3페이지 PASS,
합성 중앙/feed/local/publication 및 실제 Tk smoke PASS. 상세는
[CENTRAL_ELIGIBILITY_RESUME_RESULT.md](CENTRAL_ELIGIBILITY_RESUME_RESULT.md).
아래 retention +90일 삭제와 local seen 기반 NEW 설명은 이전 정책 이력이다.

Latest selection/management work (2026-11-03): 업로드 미리보기 왼쪽 체크, 기본 전체 선택,
전체/해제/반전·페이지 이동·선택 건수와 선택 행만 저장을 지원한다. 실적 관리 창에서 실제 DB
전체 조회/검색/정렬·6개 필드 수정·확인 후 단건/복수 삭제, user provenance·metadata cleanup·
matcher 자동 갱신을 지원한다. 전체 586 unittest와 실제 EXE 선택저장/관리/재실행 자동 검증 PASS,
외부 호출 및 orphan metadata 0. 상세는 [PERFORMANCE_MANAGEMENT_RESULT.md](PERFORMANCE_MANAGEMENT_RESULT.md).

Latest closed-taxonomy work (2026-11-03): 기존 technical 후보 20개 + 소부장만 허용한다.
technical_field/technical_fields는 후보명만 최대 3개 저장·표시하며 원문 세부어는 evidence/keywords에만 보존한다.
사용자 선택·insert·중복 수정·재분석 저장 경계에서 후보를 검증한다. 전체 572 unittest 및
실제 EXE 후보명/소부장 3분야 표시·저장·재실행·외부 호출 0 자동검증 PASS.
최신 결과는 [CLOSED_TECHNICAL_TAXONOMY_RESULT.md](CLOSED_TECHNICAL_TAXONOMY_RESULT.md)를 확인한다.
아래 세부 태그 우선 표시 설명은 이전 구현 이력이다.

Latest phrase/multilabel work (2026-11-03): 제목/독립 기술어/설명 phrase를 각각 분류하고
기술분야 margin 탈락을 제거했다. broad 분야와 상세 태그를 각각 최대 3개 보존하며,
기존 업무유형/사용자값/원문/matcher 점수는 유지한다. 진단 도구는 제목을 로컬 창에서만 표시하고
파일에는 통계만 남긴다. 실제 사용자 DB는 기본 경로에서 발견되지 않아 실데이터 전후 통계는 미측정이다.
최신 검증 범위와 남은 사항은 [PHRASE_MULTILABEL_RESULT.md](PHRASE_MULTILABEL_RESULT.md)를 확인한다.

Latest preview/tag fix (2026-11-03): 실적 미리보기는 번호·연도·관리번호·실적명·고객·기술분야·업무유형만 표시.
기존 taxonomy에 전기자동차/배터리 세부 태그를 추가하고 원문 명시 태그를 독립 판정한다.
`전기자동차 배터리팩`은 `전기자동차 · 배터리`로 표시·보존하며 모델 margin으로 미분류 처리하지 않는다.
최신 EXE 검증과 배포 정보는 [PERFORMANCE_TAG_FIX_RESULT.md](PERFORMANCE_TAG_FIX_RESULT.md)를 확인한다.

Latest local AI work (2026-11-03): 공식 MIT multilingual-e5-small INT8 ONNX/CPU 모델과
tokenizer/라이선스 동봉. 모델 resource 약 136.69MB, 기존 deterministic matcher 유지.
원본·사용자값 우선, 기술분야/업무유형/추출 키워드 보조, provenance/cosine/margin 저장,
미분류 분석/사용자 수정 보호/취소/fallback 지원. 파싱·추론은 별도 로컬 프로세스에서만 수행.
실제 EXE HTTP 차단 검증에서 외부 호출·추출형 필드 hallucination 0건, 재실행 유지 PASS.
최신 모델·품질·성능·EXE 측정은 [LOCAL_AI_ENRICHMENT_RESULT.md](LOCAL_AI_ENRICHMENT_RESULT.md)를 확인한다.

Latest local upload work (2026-11-03): `실적 업로드` toolbar 버튼, xlsx/xls/csv 로컬 reader,
다중 sheet/header/alias/heuristic 미리보기, 확인 후 기존 DB 저장·중복 유지·즉시 matcher 재연결.
중앙 scraper/Actions/Gemini/Pages/feed 및 matcher 계산 방식은 이 작업에서 변경하지 않았다.
전체 520 unittest와 실제 EXE 업로드/재실행 자동 검증 PASS. 네이티브 파일 선택창의
실제 클릭·육안 검증은 Computer Use native pipe 연결 오류로 미실시.
상세 근거는 [PERFORMANCE_UPLOAD_RESULT.md](PERFORMANCE_UPLOAD_RESULT.md)를 확인한다.

Historical retention/NEW work (2026-11-03; superseded above): 활성·마감일 미상 공고 유지,
확정 마감일 +90일 포함 보존, +91일부터 중앙/state/feed/cache 현재 snapshot에서 archive 없이 삭제.
미확인 공고는 재실행/동기화 후에도 NEW 유지, 상세 열기/확인 처리 이력은 로컬 sidecar에 저장.
중앙 Notice/Gemini/matcher/DB schema와 Actions 복원 계약은 유지한다.
최신 작업 검증은 [RETENTION_SEEN_RESULT.md](RETENTION_SEEN_RESULT.md)를 확인한다.
아래 자동 만료 없음/실행 전 cache 기반 NEW 설명은 이 정책 이전의 이력이다.

Latest UI work: Dark Night 업무 모니터링 대시보드. 상태 카드 / 비동기 GitHub 동기화 /
공고별 매칭 accordion / 앱 내부 상세 페이지로 전면 개편. 최신 검증과 배포 상태는
[DARK_NIGHT_UI_RESULT.md](DARK_NIGHT_UI_RESULT.md)를 확인한다. 아래 milestone 이력과 당시
미검증 표시는 과거 기록이며 현재 UI 동작 설명보다 우선하지 않는다.

## Last Completed Milestone
M16.1 — Windows executable packaging. PASS (2026-11-02, 사용자 제공 일반 PowerShell 설치/빌드/exe 실제 실행/Tk 정상 표시 근거). 기존 442개 + packaging 4개 = 446 unittest OK.
M16 — RIPC/KISTA 수집원 추가. PASS (2026-11-02, 사용자 제공 일반 PowerShell 실제 HTTP/전체 회귀 결과 근거).
M15 — Local Dashboard. PASS (이번 요청의 오프라인·읽기 전용 UI 범위, 2026-11-02).
M14 규칙 매칭 PASS 및 기존 공식/공개 API 유지.
M13 SQLite/CSV/검색 PASS 유지.
M12 feed 동기화의 오프라인 PASS 및 기존 계약 유지.
M10 중앙 pipeline PASS 유지. M11은 실제 GitHub 실행/공개 URL 확인 전까지 PARTIAL이며 M12 구현 완료와 구분한다.
M00~M09 PASS 유지(M05는 fixture 기반/오프라인 검증, M08 실제 API 미검증).
M08부터 V2의 번호/범위를 사용한다. 이전 RESULT의 후속 번호는 당시 계획의 이력이다.

## Current Milestone
M16.1 — **PASS**. 생성 exe: dist/notice_crawling/notice_crawling.exe. 일반 PowerShell 외부 실측에서 설치/빌드/실행/Tk 표시 성공. Codex 내부 DNS/AuthorizationManager 제한은 실행환경 이력으로 분리한다. 이번에는 문서만 갱신했으며 M17은 진행하지 않았다.
M16 — RIPC/KISTA 수집원 추가: **PASS**. 2026-11-02 사용자 제공 일반 PowerShell 실제 검증 결과로 종료했다.
RIPC SUCCESS/Notice 1건/목록 10건/기간 2026-08-07~2026-08-21, KISTA SUCCESS/Notice 1건/목록 20건/기간 2026-01-12~2026-12-31. 양쪽 title_nonempty=true.
일반 PowerShell 전체 unittest: Ran 442 tests, OK, 40.192s. Codex 내부 DNS_ERROR/11001은 실행환경 제한이며 외부 실제 HTTP 수집은 성공했다.
원본 HTML 4개와 실제 DOM/JS 요청 구조를 확인했다. RIPC AJAX JSON/HAR 보관 및 실제 2페이지 응답은 추가 관찰 사항이며 이번 종료 조건과 구분한다.
새 .contract.html 표본은 공개 텍스트를 최소 HTML로 재구성한 것으로 실제 사이트 수집 성공 증거가 아니다.
M16.1이 마지막 완료 milestone이다. 기존 Notice/feed/matcher/dashboard/DB 계약은 그대로 유지했다. M17은 진행하지 않았다.
M12 metadata/feed 검증 → 단일 atomic cache → 오류 시 마지막 정상 cache 반환 계약은 그대로다.
M11 workflow/보조 도구/문서/오프라인 검증은 완료했으나 실제 배포 확인은 계속 남아 있다.
현재 폴더에는 .git이 없다. 이전 문서의 대상은 Emoty-9s/notice_crawling(main/private)이며 이번에 원격 상태/권한을 재확인하지 않았다.
실제 파일 업로드/Git remote 설정/Secret·Variable·Pages 설정/수동 실행/공개 URL 확인은 미완료다.

## Current Architecture
- src.main이 중앙 pipeline을 실행한다. 기본 config는 모두 비활성이므로 NO_ENABLED_SITES로 종료(code 2)한다.
- src/pipeline.py가 설정/저장 검증 → registry 수집·정규화 → diff → Gemini → 전체 병합 → 저장/feed/status를 연결한다.
- M02 Notice/GeminiResult 및 enum/JSON 계약, M03 정규화/안정적 ID/hash를 제공한다.
- M04 BaseScraper가 fetch/parse/normalize/run 및 HTTP timeout/retry/User-Agent를 제공한다.
- M05 사이트 adapter 5개가 실제 HTML fixture 기반으로 list[Notice]를 반환한다.
- M16 RipcScraper는 원본 JS에 명시된 AJAX POST/JSON/#elem 상세를, KistaScraper는 실제 20행/JS view/form POST/pageIndex/DEXT5 metadata를 처리한다. 알 수 없는 요청 구조는 실패한다.
- 기존 build_mvp_registry는 5개 계약 유지, 새 build_registry가 활성 M16 소스를 추가한다. pipeline은 활성 소스에 따라 builder를 선택한다.
- 공통 HTML tree/StructureError 및 BoardScraper가 사이트 간 중복을 처리한다.
- Registry가 명시적 등록, 반환 계약 검증, 소스별 실패 격리 및 메모리 진단을 제공한다.
- M06 JsonStorage가 Notice/status JSON snapshot의 검증/load/atomic save를 제공한다.
- M07 compare_notice/compare_batch가 상태 판정, 변경 필드 및 중복 진단을 반환한다.
- M08 GeminiClient/RelevanceAnalyzer가 중앙 업계 참여 가능성을 구조화 판정하고 hash 캐시/실패 격리를 제공한다.
- 목표 흐름은 중앙 공통 JSON 배포 → 로컬 실적 매칭이다. 회사 실적/지원 의사는 중앙 판정에 포함하지 않는다.
- M09 build_feed/write_feed가 관련 공고를 공통 public JSON/metadata로 생성한다. 호출자가 시각/입력을 공급한다.
- M11 workflow가 daily/dispatch → 상태 artifact 복원 → 중앙 pipeline → 검증된 JSON pair Pages 배포를 구성한다.
- src/local_client가 중앙 모듈을 import하지 않고 public schema v1 다운로드/검증/atomic snapshot/fallback을 제공한다.
- src/local_client/performance.py가 stdlib sqlite3 기반 로컬 실적 CRUD/CSV import/검색을 제공한다. feed/중앙/AI 모듈을 import하지 않는다.
- src/local_client/matcher.py가 M12 개별 공고 dict와 M13 실적을 로컬에서 매칭한다. 네트워크/AI/embedding/시계 호출 및 저장은 없다.
- src/local_client/dashboard.py가 읽기 전용 SQLite/검증된 cache를 읽고 M14 결과를 표시용 row/text로 변환한다.
- src/local_client/ui.py가 표준 Tkinter 데스크톱 UI를 제공한다. 기존 sync CLI와 별도 진입점이며 HTTP 서버도 없다.
- 실제 GitHub 연결/실행/Pages 배포는 아직 하지 않았다. M16 실제 사이트 검증은 사용자 제공 일반 PowerShell 결과로 PASS이며 M17 이후는 착수하지 않았다.

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
- **442 unittest OK**: 기존 414개 + 원본 HTML 보강 28개. M16 누계 90개 + M15까지 352개. 실제 상세 Notice 생성/오프라인 통합을 검증했으며 실제 HTTP 수집 성공과 구분한다.
- 사용자 제공 일반 PowerShell 실제 HTTP: RIPC Notice 1건/목록 10건, KISTA Notice 1건/목록 20건 SUCCESS. 외부 전체 회귀 442개 OK/40.192s로 M16 PASS.
- 두 소스 registry→pipeline→feed→M12 mock cache→기존 matcher/dashboard 통합, 실패 시 이전 데이터 보존 및 연도별 stable URL identity 검증.
- M15 당시 별도 실제 Tk UI_SMOKE_PASS/--help exit 0 이력 유지. M16에서 해당 코드를 수정하지 않았다.
- M15 공고/순위/총점/규칙·근거/합계/빈 결과/오류/한글/결정성/TOP N 및 UI 호출 후 DB/cache 불변 검증.
- 실제 Tk에서 공고 선택·매칭·입력 변경·이전 결과 초기화·누락 파일 오류 흐름을 확인했다.
- 매칭 점수/설명 합계/결정성/중복 방지/한글/TOP N/동점/100건 초과 DB 전체 평가 및 feed cache→DB 로컬 통합 검증.
- SQLite 최초 생성/CRUD/중복/CSV 전체 rollback/재실행 지속성/검색/DB 오류 보존 및 feed·Gemini 무호출 검증.
- M12 정상/동일/빈 feed, timeout/HTTP/JSON/schema 오류 fallback, cache 출처/손상 검증 및 저장 실패 시 이전 pair 보존을 검증했다.
- 사용자 제공 실제 list.html/detail.html 10개를 수정 없이 사용.

## Business Context / M01 Coverage
- 사용자 조직은 특허법인. 수행/협력기관 모집 및 입찰 관점으로 대상 적합성을 판단한다.
- KIPA IP 디딤돌 수혜기업 전용 게시판은 범위 제외다.
- 원본 XLSB 49 URL → 47 수집원 coverage와 셀 참조/원본 해시 유지.
- M01 MVP는 총 7개다. M05에서 구현한 것은 아래 5개뿐이다.
  khidi_business, kised_bid_public, rda_bid, seoul_rnd_notice, kipa_bid.
- M16에서 KISTA/RIPC 원본 DOM/JS 기반 adapter를 보정했다. 사용자 제공 일반 PowerShell 결과로 각 최소 1건 실제 HTTP 수집을 확인하여 M16 PASS로 집계한다. 상시 운영/배포 여부와 구분한다.
- RIPC 대상은 사용자 정정에 따라 partner/tenderNotice 협력기관 입찰사업 공고다. 이전 applicant 지원기업 공고용 경로/parser/표본을 교체했다. 배정예산 포함 7컬럼, 상세 공고기간/단위사업 라벨을 사용하며 예산 schema는 추가하지 않았다.
- 기존 config/sites.yaml의 enabled=false는 유지한다. 테스트에서만 복사 config를 활성화한다.

## Known Broken / Pending
- 원본 경로 blocker는 해소했다. tests/fixtures/m16_live/ripc 및 kista의 네 HTML을 실제로 읽고 URL session 91곳을 제거했다. HAR/실제 RIPC AJAX 응답/실제 2페이지 응답은 제공되지 않았다.
- M16 종료 조건의 blocker 없음. Codex 내부 DNS_ERROR/11001은 실행환경 제한이며 동일 PC 일반 PowerShell에서 각 Notice 1건 실제 HTTP 수집에 성공했다(사용자 제공 근거).
- 원본 DOM/JS의 RIPC getNoticeList.do POST/JSON 키, KISTA view/pageIndex form POST 및 첨부 설정과 외부 live 성공을 구분 기록했다. 원본 JSON/HAR 자체는 보관되지 않았다.
- 기본 max_pages=3(1~20). 실제 원본 JS/form 기반 POST 전달 및 mock 2페이지를 검증했다. 실제 2페이지 HTTP 순회는 미검증이다.
- KISTA DEXT5 설정 파일 경로 3개는 확인했으나 실제 download handler/접근 성공은 미검증이다. RIPC 첨부 href 2개도 HTTP 다운로드는 하지 않았다.
- 두 source enabled=false 유지. validation/status는 사용자 제공 외부 live/전체 회귀 결과에 따라 PASS로 갱신했다. 자동 운영 활성화는 하지 않았다.
- M15 오프라인 UI 구현 blocker 없음. Tk 포함 Python/로컬 데스크톱이 필요하며 현재 환경 Tk 8.6에서 smoke 확인했다.
- UI는 기존 정상 M12 snapshot/M13 DB만 읽고 생성·수정하지 않는다. 기본 파일이 없으면 상태 오류이며 UI가 대신 다운로드/초기화하지 않는다.
- 온라인 feed 갱신/원문 브라우저 실행/NEW·UPDATED 추론은 이번 요청 범위에서 제외했다. URL은 표시만 하며 원본 feed 상태를 추가하지 않는다.
- 몇 주간 실사용 Gate는 미수행이다. docs/usage/ISSUES.md 및 IMPROVEMENTS.md에 비식별 피드백 기록 구조를 제공했다.
- M14 구현 blocker 없음. 기준 연도는 필수 입력이며 기본 최근 3년(현재+이전 2년)을 적용한다. 0점 결과도 TOP N에 포함한다.
- 매칭은 NFKC/casefold 기반 용어·문구 일치와 명시적 category 관계다. 형태소/임의 동의어 추론은 없으며 실표본 가중치 조정은 사용자 로컬 검토 사항이다.
- 매칭은 전체 실적을 메모리로 읽는다. 결과 저장/최적화는 없으며 표시는 별도 M15 UI가 담당한다. M11/M12 실제 배포·다운로드 제한은 별도 유지한다.
- M13 구현 blocker 없음. 실제 실적/운영 DB는 생성하지 않았으며 테스트는 임시 DB/합성 CSV만 사용했다.
- 로컬 실적 DB 기본 local/performance.db, CSV 권장 local/imports/. local/ 전체와 DB/journal/WAL/SHM은 Git 제외다.
- 실적 schema v1 자동 migration/백업/손상 복구/대량 CSV streaming은 없다. CSV 오류/중복은 전체 import를 취소한다. 매칭/읽기 전용 UI는 별도 M14/M15가 담당한다.
- M12 오프라인 구현 blocker 없음. M11 공개 URL 미확정으로 실제 GitHub feed 다운로드는 미검증이다.
- 로컬 cache는 local/cache/snapshot.json 한 파일에 두 JSON과 출처 URL을 저장한다. 단일 writer 전제이며 자동 재시도/스케줄/ETag/과거 이력은 없다.
- 정상 cache가 없는 최초 네트워크 실패 또는 손상 cache+다운로드 실패는 SyncError/CLI exit 2다. 빈 정상 결과로 숨기지 않는다.
- M11 blocker: 현재 폴더에 .git이 없으며 업로드/Actions/Pages 설정·실행은 이번 작업에서 수행하지 않았다.
- 과거 connector/UI 시도는 이전 작업의 이력이다. 이번에는 실제 Secret/Variable/Pages 설정 및 원격 권한을 확인하지 않았다.
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
- M05 당시 실제 네트워크 smoke는 미실행이었다. M16 Codex 내부 smoke는 DNS 오류였으나 일반 PowerShell 실제 HTTP 검증은 양쪽 SUCCESS였다(사용자 제공 근거).
- 사이트별 상세 1개 표본만 검증했으며 운영 전체 유형/페이지에 대한 보증은 아니다.
- 기존 M05는 첫 목록 페이지 정책 그대로다. M16만 실제 원본 JS/form POST 기반 유한 페이지 window를 추가했으며 실제 pagination HTTP 응답은 미검증이다.
- 알려지지 않은 빈 목록 안내행/변형 구조는 []로 숨기지 않고 StructureError로 실패한다.
- KIPA 표본은 본문이 짧고 세부 내용은 첨부/나라장터에 있다. 외부/첨부 내용은 추론하거나 분석하지 않는다.
- 서울 R&D 편집기 HTML 일부 속성이 비정상이지만 fixture 본문은 정상 추출된다.
- 목록/상세 제목 불일치 시 실패하고 목록을 다시 수집해야 한다.
- KISTA 페이지 이동/RIPC 목록·페이지 요청, 기타 비선정 소스는 기존 M01 후속 제한이다.

## Important Files
- src/scrapers/ripc_pms.py / kista_ippro.py / _portal.py: M16 별도 adapter/robots/관찰된 POST/metadata/유한 페이지 처리.
- tests/_m16_cases.py / test_ripc_pms.py / test_kista_ippro.py / test_m16_integration.py / test_m16_smoke.py: 신규 62개 계약 테스트.
- tests/fixtures/m16_contract/README.md: 원본이 아닌 재구성 표본의 출처/합성 범위/제한.
- tests/test_m16_live.py / tests/fixtures/m16_live/README.md: 원본 HTML 4개 기반 보강 28개/원본과 mock 차이/세션 제거/남은 실제 HTTP 검증.
- tools/m16_smoke.py / docs/progress/M16_RESULT.md: 실제 HTTP 최소 probe/외부 PowerShell 성공 근거/Codex DNS 제한/요청 분석/추가 관찰 사항.
- src/local_client/ui.py / dashboard.py: Tk UI/읽기 전용 loader/기존 matcher 연계 및 표시 presenter.
- tests/test_dashboard.py / tests/ui_dashboard_smoke.py: M15 24개 unittest/별도 실제 widget smoke.
- docs/progress/M15_RESULT.md / docs/usage/{ISSUES,IMPROVEMENTS}.md: 구현 범위/검증/사용/비식별 실사용 기록 구조.
- src/local_client/matcher.py / tests/test_matcher.py: 가중치/범주 관계/점수 근거/결정적 TOP N 및 27개 로컬 테스트.
- docs/progress/M14_RESULT.md: 점수/입력/정규화/중복/정렬/기준 연도/API/제한 및 검증 결과.
- src/local_client/performance.py / tests/test_performance.py: 독립 SQLite 실적 모델/CRUD/CSV/검색 및 28개 테스트.
- docs/progress/M13_RESULT.md: 실적 필드/DB schema/CSV 형식/API/rollback/로컬 데이터 경계 및 검증 결과.
- src/local_client/sync.py / __main__.py: 독립 로컬 동기화 API/CLI, schema 검증 및 atomic cache/fallback.
- tests/test_local_client.py / docs/progress/M12_RESULT.md: 오프라인 24개 테스트/실행 방법/cache 계약/제한.
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

2026-11-02 원본 HTML 보정 후 최종 전체 재실행 결과 442 tests OK, exit code 0, 51.572초 (M16 누계 90개). 각 실제 상세에서 Notice를 생성했으며 실제 HTTP 수집 성공과 구분한다. 기존 테스트/M05 fixture는 바꾸지 않았다.
위 51.572초는 Codex 내부 회귀 이력이다. 최종 사용자 제공 일반 PowerShell 회귀 결과는 Ran 442 tests / OK / 40.192s다.
`python -m tools.m16_smoke --source ripc_pms kista_ippro`: Codex 내부는 DNS_ERROR/11001/exit 1 이력. 일반 PowerShell에서는 RIPC SUCCESS/Notice 1/목록 10, KISTA SUCCESS/Notice 1/목록 20(사용자 제공 실측)으로 M16 PASS 조건을 충족했다.
`python tests/ui_dashboard_smoke.py` → 실제 Tk UI_SMOKE_PASS, exit code 0. `python -m src.local_client.ui --help` → exit code 0.
추가 선택 검증: `node --test tests/test_actions_state_selector.cjs` → 6 tests PASS. Node 설치는 추가하지 않았다.
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
M16 PASS로 종료했다. M17은 진행하지 않는다. 별도 잔여 작업은 아래 M11/M12 검증이며, 실제 2페이지 응답/다운로드 handler 확인은 추가 관찰 사항으로 남긴다.
실제 GitHub 저장소/Secret/Variable/사이트 활성화/Pages 설정 후 최초 수동 workflow 및 두 JSON URL을 확인해 M11을 완료한다.
그 URL을 src.local_client --base-url로 지정해 M12 실제 다운로드 및 오프라인 cache fallback을 확인한다.
M13 실적 API/CSV 형식은 docs/progress/M13_RESULT.md를 참고해 사용자 로컬에서 확인할 수 있다.
M14 match_notice/match_store API로 사용자 로컬 표본의 추천 근거를 검토할 수 있다. 사용법은 docs/progress/M14_RESULT.md 참고.
M15 UI: `python -m src.local_client.ui` → 기존 로컬 파일 지정/다시 읽기 → 공고 선택 → 명시적 기준 연도/TOP N → 매칭/근거 확인.
비식별 실사용 피드백은 docs/usage에 기록할 수 있다. M17 이후는 사용자 요청 없이 진행하지 않는다.
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
  M09에서 이 조건을 확인하여 feed를 생성하고 M10이 연결한다. 실적 DB/매칭은 이후 M13/M14에서 로컬 모듈로 별도 구현했다.

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
- 실제 GitHub 실행/수동 성공/배포 URL 확인이 남아 있으므로 M11은 PARTIAL이다. M11 당시 마지막 완료는 M10이었으며 이후 M12~M15 로컬 구현/검증은 별도 완료했다.

## M11 Repository History / Manual Handoff

- 이전 기록: https://github.com/Emoty-9s/notice_crawling, ID 1439083905, main, private 및 관리자/push 권한 확인 이력이 있다.
  2026-11-02에는 이를 재확인하지 않았다. 현재 로컬에는 Git 저장소/remote가 없다.
- 이전 .run/M11_UPLOAD.zip 및 .run/M11_PUSH_MANIFEST.json은 이번 보완 전 산출물일 수 있다.
  현재 소스 파일을 반영해야 하며 .venv/.env/credential/임시 산출물은 제외한다.
- 수동 순서: 압축 해제 파일을 main에 반영 → GEMINI_API_KEY Secret → GEMINI_MODEL Variable → 구현 source 활성화
  → private 지원 플랜/Pages Actions source/권한 확인 → 최초 bootstrap_state=true dispatch → build/deploy 및 Gemini SUCCESS 확인
  → 실제 page_url의 notices.json/metadata.json 공개 접근 확인.
- 정확한 설정/주의사항은 docs/operations/GITHUB_PAGES.md 및 docs/progress/M11_RESULT.md에 있다.
- private 유지. M11 실제 로그/URL 증거가 없으므로 M11은 PASS로 변경하지 않는다. M12는 현재 별도 오프라인 PASS다.

## M12 Local Sync Contract / Handoff

- `python -m src.local_client --base-url URL [--cache-dir PATH] [--timeout SECONDS]`.
- `FeedClient(base_url, cache_dir=..., timeout=30, transport=...).sync()` → SyncResult(status, feed, metadata, error_code).
- metadata.json → notices.json 순으로 다운로드하고 UTF-8/strict JSON/schema_version=int 1/공개 15필드/중복 ID/시각/count를 검증한다.
- 중앙 pipeline/AI/scraper/storage import 및 Gemini 호출 없음. 표준 라이브러리만 사용한다.
- local/cache/snapshot.json에 base_url/feed/metadata를 묶어 write/flush/fsync/close/os.replace 한 번으로 commit한다.
- UPDATED/UNCHANGED는 CLI exit 0. 동일 pair는 재저장하지 않는다. FALLBACK은 기존 정상 pair+원인 코드/exit 1.
- 네트워크/JSON/schema/pair 검증/저장 오류는 같은 URL의 검증된 cache만 반환한다. 정상 cache 없으면 SyncError/exit 2.
- load_cache()는 HTTP 없이 검증된 envelope를 읽는다. 손상 cache는 정상 다운로드 성공 시에만 교체 가능하다.
- timeout 기본 30초/요청별 최대 16 MiB. 자동 재시도/동시 writer/업데이트 rollback 방지/과거 snapshot 이력은 없다.
- M12 실제 GitHub HTTP는 M11 배포 URL 확인 후 검증한다. M13 DB/M14 매칭/M15 오프라인 UI는 별도 로컬 검증 완료다.

## M13 Local Performance Contract / Handoff

- `from src.local_client.performance import Performance, PerformanceStore`.
- PerformanceStore(path=None, timeout=5)는 기본 local/performance.db를 생성/검증한다. application_id=PERF, user_version=1이다.
- Performance는 10필드 frozen dataclass. ID/과제명 필수, 연도 int 또는 None, keywords/attorneys는 tuple이며 list 입력을 허용한다.
- create(record)/get(id)/update(record)/delete(id)/search(query='', year=None, limit=100, offset=0)/import_csv(path, encoding='utf-8-sig').
- 중복 ID는 명시적 오류이며 upsert하지 않는다. get 누락은 None, delete 누락은 False, update 누락은 오류다.
- CSV는 10개 header 필수/순서 자유, 목록 세미콜론 구분, 전체 사전 검증 후 단일 transaction. 어느 행/DB 오류든 이번 import 전체 rollback.
- 검색은 casefold 부분 문자열이며 parameter binding을 사용한다. year 내림차순/ID 오름차순, 점수/공고 매칭은 없다.
- DB/CSV 오류는 실적 내용 없는 고정 코드(가능한 CSV 줄 번호 포함)를 제공하며 기존 DB를 초기화하지 않는다.
- 중앙/AI/feed/sync와 연결하지 않는다. local/와 DB 파일은 Git 제외이며 실적을 HTTP/GitHub/Gemini로 보내지 않는다.
- M13 당시 28개/전체 301 unittest PASS. 이후 M14 매칭/M15 읽기 전용 UI를 별도 모듈로 추가했다.

## M14 Local Matcher Contract / Handoff

- `from src.local_client.matcher import MatchWeights, match_notice, match_store`.
- match_notice(notice, performances, reference_year=..., top_n=5, weights=..., recent_years=3, category_groups=...).
- match_store(notice, store, ...)는 한 SELECT로 전체 실적을 읽는다. M13 search 기본 100건에 잘리지 않으며 DB 오류를 전파한다.
- MatchResult는 performance_id/score/matched_terms/reasons와 to_dict()를 제공한다. score는 각 reason.points 합계다.
- 기본 가중치는 MatchWeights 한 곳: technical_field=5/work_type=5/keyword=2/category=3/title=2/recent=1.
- category/participation_type/keywords/title/summary만 소비한다. 기술/업무 용어 일치, 고유 keyword, 명시적 category 관계, 제목 token, 최근 연도 규칙이다.
- NFKC/casefold/대시/공백 정규화 후 중복을 제거한다. keyword는 고유어마다 1회, title/category는 각 1회다.
- reference_year 필수, recent_years 기본 3. 미래/미상 연도는 보너스 없음. 시계를 읽지 않아 입력/기준 연도가 같으면 결과가 같다.
- 정렬 score 내림차순/ID 오름차순, top_n=0 허용, 0점 결과도 포함한다. 중복 실적 ID는 오류다.
- 입력/cache/DB 불변. 중앙/GitHub/Gemini/embedding 호출 및 실적 외부 전송 없음. M14 27개/전체 328 unittest PASS.
- M15 UI는 이후 추가한 표시 계층이며 위 M14 점수/정렬/공개 API는 변경하지 않았다.

## M15 Read-only UI Contract / Handoff

- `python -m src.local_client.ui [--cache PATH] [--db PATH] [--reference-year YEAR] [--top-n N]`.
- stdlib Tkinter, 기존 기본 snapshot/DB 위치 사용. UI에서 파일 경로/필터/연도/TOP N을 지정한다.
- `load_dashboard`는 cache strict JSON/M12 공개 검증과 SQLite mode=ro/query_only로 데이터를 읽고 공개 Performance 모델로 복원한다.
- PerformanceStore 초기화/CRUD/sync/download/save/원문 브라우저 호출 없음. 누락·손상 파일은 오류이며 자동 생성/빈 초기화하지 않는다.
- `recommendation_rows`는 기존 matcher.match_notice를 호출하고 ranking/project_name/total_score/rule_total/sum_matches를 표시용으로 결합한다.
- 공고 상세/기관·category·검색/추천 선택/규칙별 points·terms/총점·합계 확인을 제공한다. 상세 text는 읽기 전용이다.
- 기준 연도 자동값 없음. TOP N 기본 5. 경로 변경은 로드 데이터까지 무효화하며 선택/조건 변경 시 이전 추천을 제거한다.
- M15 24개/전체 352 unittest PASS, 실제 Tk widget smoke PASS. DB/cache 전후 bytes 불변 및 외부 통신 금지 확인.
- 별도 잔여 작업: M11 배포 URL 확인 → 이후 M12 실제 GitHub HTTP 다운로드 검증. 이번에 수행하지 않았다.
- M15 요청의 UI 범위만 PASS이며 장기간 실사용 Gate는 별도 관찰 사항이다. 이후 M16은 사용자 제공 일반 PowerShell live/회귀 근거로 PASS 종료했다.

## M16 Sources / Handoff — PASS

- 대상: ripc_pms=partner/tenderNotice/list.do, 상세 partner/tenderNotice/info.do. 지원기업 공고가 아닌 협력기관 입찰사업 공고다. kista_ippro=ippro//com/iprndMain/selectBusinessAnnounceList.do?bbsType=ac.
- 별도 RipcScraper/KistaScraper, 기존 BaseScraper transport/UA/timeout/retry/실패 격리 사용. 추가 Session/의존성/AI scraping 없음.
- 원본 HTML 4개를 확보했다. RIPC AJAX/JSON/#elem, KISTA 20행/JS 상세 호출/form POST/pageIndex/encoded contents/DEXT5를 보정했다. 미확인 요청/잘못된 JSON/페이지 불일치는 실패한다.
- robots 확인 후 허용 경로만 요청하며 403/서버/DNS 실패는 우회하지 않는다. 기본 max_pages=3, 최대 20, 한도 warning/중복 제거.
- 연도+sequence의 canonical 상세 URL을 기존 M03 stable URL 분기로 처리한다. 모델/enum/hash/feed/cache/DB/matcher/dashboard 변경 없음.
- attachment 모델 계약은 없어 scoped 절대 href tuple 검증만 제공하며 Notice/feed에 필드를 추가하거나 파일을 내려받지 않는다.
- source 설정/지원 소스만 확장하고 기존 build_mvp_registry 5개 계약/기존 테스트는 유지했다. 기본 enabled=false/47개 coverage 유지.
- 신규 누계 90개/전체 442 unittest OK. 원본 HTML 보강 28개 포함. RIPC JSON/2페이지 응답은 mock이며 원본 캡처가 아님을 명시했다.
- 실제 HTTP: 사용자 제공 일반 PowerShell 결과 RIPC SUCCESS/Notice 1/목록 10, KISTA SUCCESS/Notice 1/목록 20. 전체 442 tests OK/40.192s로 M16 PASS. Codex 내부 DNS_ERROR/11001은 실행환경 제한으로 별도 기록했다.
- RIPC JSON/HAR 보관/실제 2페이지 응답/KISTA 다운로드 handler는 추가 관찰 사항이며 검증 완료로 표시하지 않는다. 이번 종료 조건의 blocker는 없다.
- 기존 별도 잔여 작업은 M11 배포 URL 확인 → 이후 M12 실제 GitHub HTTP 다운로드 검증이다. M17은 미착수다.
