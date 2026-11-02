# 사업공고 모니터링 시스템

공고 사이트의 신규/수정 공고를 수집하고, Gemini가 특허법인/특허사무소의
수행 주체 참여 가능성을 판정하여 공통 JSON으로 제공합니다.
현재 개발 범위는 `MILESTONES_V2.md`를 따릅니다. 회사 실적 매칭은 로컬 영역에서 수행합니다.

중앙 구현은 **M10 — Central End-to-End Pipeline**, 로컬 구현은 **M12 feed 동기화 / M13 실적 DB / M14 규칙 매칭 / M15 읽기 전용 UI**입니다.
사이트 설정 → 수집/정규화 → diff → Gemini → 저장 → feed → scraper status를 연결했습니다.
기본 사이트 설정은 모두 비활성이므로 기본 명령은 외부 호출 전에 설정 오류로 종료합니다.

## 환경 및 실행

Python 3.13 기준이며, 프로젝트 루트에서 PowerShell로 실행합니다.
가상환경 활성화 없이 아래 명령을 사용할 수 있습니다.

```powershell
& 'C:\Users\이재혁\AppData\Local\Python\pythoncore-3.13-64\python.exe' -m venv .venv
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m src.main
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

현재 기본 실행 출력: `CONFIGURATION ERROR: NO_ENABLED_SITES: ...` (종료 코드 2).

실제 실행에는 `config/sites.yaml`에서 구현된 사이트를 명시적으로 활성화하고,
프로세스 환경변수 `GEMINI_API_KEY`, `GEMINI_MODEL`을 설정해야 합니다.
`.env.example`은 이름 예시이며 `.env` 자동 로딩은 없습니다. 키를 코드/JSON에 저장하지 마세요.
구현된 사이트는 khidi_business, kised_bid_public, rda_bid, seoul_rnd_notice, kipa_bid입니다.
그 외 미구현 사이트를 활성화하면 설정 오류로 종료합니다. RIPC/KISTA는 아래 M16의 잠정 지원 범위를 확인해야 합니다.
기본 config의 enabled 값은 변경하지 않았습니다.

```powershell
.\.venv\Scripts\python.exe -m src.main --help
.\.venv\Scripts\python.exe -m src.main --config .\config\sites.yaml --data-dir .\data --public-dir .\public
```

설정이 갖춰진 실행은 실제 사이트/API 요청 및 파일 저장을 수행합니다.
종료 코드는 0=정상, 1=사이트/분석 일부 실패 후 결과 저장, 2=설정/저장/검증 오류입니다.
표준 라이브러리 unittest 테스트는 실제 HTML fixture/fake Gemini/임시 저장소만 사용하며 외부 패키지가 필요 없습니다.

## 기본 구조와 예정 역할

```text
src/main.py          중앙 명령 진입점/설정 preflight
src/pipeline.py      중앙 orchestration 및 기존 데이터 병합
src/core/            공통 모델/정규화/저장/diff
src/scrapers/        사이트별 수집과 registry
src/ai/              중앙 Gemini 판정/캐시/실패 격리
src/renderer/        공개 JSON feed 생성
src/local_client/    feed 동기화/실적 DB/로컬 매칭/오프라인 Tk UI
config/              사이트/중앙 판정 정책
data/                notices.json / scraper_status.json (실행 시 생성)
public/              notices.json / metadata.json
tests/test_smoke.py  모듈 실행 smoke test
tests/fixtures/      실제 HTML 테스트 입력 자료
docs/site-audit/     사이트 조사
docs/progress/       마일스톤 결과와 인계 상태
```

빈 디렉터리는 `.gitkeep`, Python 패키지는 `__init__.py`로 유지합니다.
실패/빈 목록/비활성/이번에 미관측된 공고도 기존 저장 기록은 보존합니다.
Gemini 실패 이력도 저장하되 일반 feed에는 현재 유효한 SUCCESS/relevant 공고만 포함합니다.
파일별 atomic write이며 여러 파일 전체 transaction이나 동시 writer 병합은 제공하지 않습니다.
M11 daily/수동 Actions 및 Pages 배포 workflow를 추가했습니다. 실제 저장소 연결·배포는 미검증입니다.
GitHub의 Secret/Variable, 사이트 활성화, Pages 설정, 최초 state bootstrap은
[운영 설정 안내](docs/operations/GITHUB_PAGES.md)를 따릅니다. 현재 설정 그대로는 실운영 실행이 중단됩니다.

## 로컬 feed 동기화 (M12)

실제로 확인한 Pages 배포 디렉터리 URL을 지정합니다. 아래 주소는 형식 예시입니다.

```powershell
.\.venv\Scripts\python.exe -m src.local_client --base-url 'https://<owner>.github.io/<repo>/'
.\.venv\Scripts\python.exe -m src.local_client --help
```

중앙 pipeline/Gemini 설정 없이 metadata.json과 notices.json을 검증하고 local/cache/snapshot.json에 함께 atomic save합니다.
--cache-dir 및 --timeout으로 저장 위치/요청 제한 시간을 지정할 수 있습니다. 기본 timeout은 30초입니다.
네트워크/JSON/schema/저장 오류에는 같은 URL의 마지막 정상 cache를 사용합니다.
종료 코드는 0=갱신 또는 동일 데이터, 1=cache fallback, 2=사용할 정상 cache 없음 또는 설정 오류입니다.
상세 API/검증/제한은 [M12 결과](docs/progress/M12_RESULT.md)를 참고합니다.

## 로컬 실적 DB (M13)

실적은 stdlib sqlite3 기반 local/performance.db에만 저장합니다. 생성/등록/조회/수정/삭제/CSV import/검색을 Python API로 제공합니다.

```python
from dataclasses import replace
from src.local_client.performance import Performance, PerformanceStore

store = PerformanceStore()
store.create(Performance(performance_id='P001', project_name='예시 과제', year=2025, keywords=['반도체']))
record = store.get('P001')
store.update(replace(record, notes='예시 메모'))
results = store.search('반도체', year=2025)
count = store.import_csv('local/imports/performances.csv')
store.delete('P001')
```

CSV는 performance_id/project_name/client/year/technical_field/work_type/keywords/description/attorneys/notes의 10개 header를 사용합니다.
keywords/attorneys는 세미콜론 구분이며 UTF-8 BOM을 허용합니다. 한 행이라도 오류/중복이면 이번 import 전체를 취소합니다.
중복 ID는 자동 덮어쓰지 않습니다. local/ 전체와 DB 파일은 Git 제외이며 실적은 중앙/GitHub/Gemini로 전송하지 않습니다.
정확한 필드/CSV/API/오류 계약은 [M13 결과](docs/progress/M13_RESULT.md)를 참고합니다.

## 로컬 실적 매칭 (M14)

M12의 개별 공고와 M13 실적을 외부 API/Gemini/embedding 없이 평가합니다.

```python
from src.local_client.matcher import MatchWeights, match_store

notice = snapshot['feed']['notices'][0]  # M12 검증된 cache
results = match_store(notice, store, reference_year=2026, top_n=5)
payload = [result.to_dict() for result in results]
custom_weights = MatchWeights(keyword=3, title=0)
```

기본 점수는 기술분야 5/업무유형 5/고유 키워드당 2/category 3/제목 2/최근 실적 1입니다.
기준 연도를 명시하며 기본 최근 3년을 사용합니다. 반환값은 score/matched_terms/규칙별 근거를 포함합니다.
동점은 ID 오름차순이며 중복 키워드는 중복 가산하지 않습니다. DB/cache를 변경하거나 실적을 외부로 보내지 않습니다.
자세한 규칙과 가중치 수정 방법은 [M14 결과](docs/progress/M14_RESULT.md)를 참고합니다.

## Dark Night 업무용 대시보드

Tk를 포함한 Python의 표준 Tkinter로 실행합니다. 웹 서버/추가 프레임워크/패키지 설치는 필요 없습니다.

```powershell
.\.venv\Scripts\python.exe -m src.local_client.ui
.\.venv\Scripts\python.exe -m src.local_client.ui --cache '.\local\cache\snapshot.json' --db '.\local\performance.db' --reference-year 2026 --top-n 5
.\.venv\Scripts\python.exe -m src.local_client.ui --help
```

앱이 먼저 표시된 뒤 GitHub 공개 feed를 백그라운드에서 동기화합니다.
**GitHub 상태 → 7개 기관의 마지막 중앙 수집 상태 → 신규 공고 → 카드별 실적 매칭 펼치기** 순서입니다.
제목을 누르면 앱 내부 상세 페이지로 이동하고, 원문 보기 버튼을 눌렀을 때만 기본 브라우저를 엽니다.
추천 선택용 별도 패널은 제거했습니다. DB 경로와 feed/cache 경로는 상단 설정·정보에서 지정합니다.
기준 연도는 자동으로 현재 연도를 사용하지 않습니다. 명령에서 생략하면 화면에서 직접 입력해야 합니다.
TOP N은 기본 5이며 0 이상으로 조정할 수 있습니다. 예시의 2026은 사용자가 지정한 기준 연도입니다.
제목·기관·분류·키워드 검색, 실적 순위·과제명·총점, 규칙별 점수·근거·합계 일치 여부를 표시합니다.

UI는 기존 matcher를 그대로 호출하고 DB를 SQLite mode=ro로 읽습니다. 실적 DB를 생성·수정하거나 업로드하지 않습니다.
DB가 없어도 공고는 볼 수 있습니다. 매칭에 사용할 DB는 기존 M13 절차로 준비합니다.
동기화 실패 시 같은 feed 주소의 마지막 정상 cache를 사용하고 노란색 상태를 표시합니다. cache도 없으면 빨간색 오류입니다.
`--offline`은 기존 cache만 표시하고 네트워크를 사용하지 않습니다. `--base-url`로 공개 feed 디렉터리를 지정할 수 있습니다.
NEW/UPDATED는 이번 앱 실행 전 cache와 비교한 표시이며 중앙 분석 상태를 변경하지 않습니다.
기준 연도/TOP N 변경 후 이전 매칭은 무효화됩니다.

기관 상태는 `source_status.json`의 마지막 중앙 수집 결과만 표시합니다. 로컬에서 기관 사이트를 검사하지 않습니다.
이 선택적 문서가 미배포/누락되면 회색, 저장된 상태를 사용하면 저장 상태와 확인 시각을 표시합니다.
공개 projection은 7개 허용 source의 `source_id/status/checked_at/notices_found`만 포함하며 private state나 오류 메시지는 공개하지 않습니다.
기존 notices.json/metadata.json 및 state artifact 계약은 유지합니다.

실사용 관찰은 [이슈](docs/usage/ISSUES.md)와 [개선 후보](docs/usage/IMPROVEMENTS.md)에 비식별 내용으로 기록할 수 있습니다.
현재 UI·exe 검증은 [Dark Night 결과](docs/progress/DARK_NIGHT_UI_RESULT.md)를 확인합니다.

## 인계

### Windows 실행파일 (M16.1 PASS)

일반 PowerShell에서 PyInstaller 빌드와 실제 exe 실행·GitHub 동기화·Tk UI를 직접 검증했습니다.
dist/notice_crawling/notice_crawling.exe를 더블클릭하면 실행됩니다. 실행하는 PC에는 Python/가상환경이 필요 없습니다.

개발자가 다시 빌드하려면 프로젝트의 가상환경이 준비된 일반 PowerShell에서 다음을 실행합니다.

```powershell
.\build_windows.ps1
```

빌드 스크립트는 requirements-build.txt의 PyInstaller를 프로젝트 .venv에만 설치하고 해당 앱의 기존 build/dist 산출물만 정리합니다.
배포 시 dist/notice_crawling의 README.txt와 _internal을 포함한 폴더 전체를 복사해야 합니다. exe만 따로 복사하지 마세요.
GUI는 Dark Night 모니터링 대시보드이며 onedir/windowed로 구성했습니다. 검증 근거는 [최신 UI 결과](docs/progress/DARK_NIGHT_UI_RESULT.md)를 확인하세요.

기본 외부 데이터 경로는 %LOCALAPPDATA%/NoticeCrawling/cache/snapshot.json 및 %LOCALAPPDATA%/NoticeCrawling/performance.db입니다.
기존 정상 파일은 설정에서 지정할 수 있고 --cache/--db 옵션도 유지합니다. 공개 공고 cache만 동기화하며 실적 DB는 생성·수정하지 않습니다.
UI가 config/sites.yaml을 읽지 않으므로 해당 config/중앙 scraper/개발 fixture/개인 DB/cache는 번들하지 않습니다. Tk/Python/SQLite runtime은 PyInstaller가 수집합니다.

### M16 RIPC / KISTA — PARTIAL

별도 RipcScraper/KistaScraper와 기존 중앙 pipeline/feed 연결을 추가했습니다.
대상은 [RIPC 협력기관 입찰사업 공고](https://pms.ripc.org/pms/biz/partner/tenderNotice/list.do)와
[KISTA 협력기관 모집공고](https://biz.kista.re.kr/ippro//com/iprndMain/selectBusinessAnnounceList.do?bbsType=ac)입니다.
M14 matcher/M15 dashboard 및 Notice/feed/cache/DB schema는 변경하지 않았습니다.
사용자 정정에 따라 RIPC 목록/상세를 partner/tenderNotice 경로로 수정하고 재구성 표본도 교체했습니다.
배정예산 포함 7컬럼과 상세 공고기간/단위사업 라벨을 처리합니다. 배정예산 저장 필드는 추가하지 않았습니다.

**현재 실운영 수집 완료가 아닙니다.** 두 도메인 직접 HTTP가 DNS 오류 11001로 실패했습니다. 두 source는 기본 비활성입니다.
사용자 제공 원본 HTML 4개를 tests/fixtures/m16_live에서 확인하고 실제 DOM/JS에 맞춰 parser를 보정했습니다. 세션 ID는 제거했습니다.
RIPC는 목록 shell의 getNoticeList.do POST/JSON 계약과 상세 #elem 본문을 처리합니다. 실제 AJAX JSON 응답은 아직 제공되지 않았습니다.
KISTA는 실제 목록 20행, view(연도,ID)의 상세 form POST, pageIndex POST pager, hidden contents를 처리합니다.
각 실제 상세에서 Notice 생성과 기존 feed/cache/matcher/dashboard 연계를 검증했습니다. RIPC 목록 JSON과 2페이지 응답은 명시적 mock으로 검증했습니다.
기존 m16_contract는 합성 입력 회귀 검사만 담당합니다. 원본과 차이/한계는 [fixture 설명](tests/fixtures/m16_live/README.md)에 기록했습니다.

기존 build_mvp_registry는 5개 계약 그대로이며 새 build_registry가 명시적으로 활성화한 M16 소스를 추가합니다.
M16 페이지 window는 max_pages 기본 3/범위 1~20이며 원본 JS/form에서 확인한 POST 필드로 순회합니다. 실제 2페이지 HTTP 성공은 미검증입니다.
상세 연도+sequence URL로 기존 M03 ID를 생성하고 누락 날짜/category는 기존 nullable 계약을 따릅니다.
RIPC 첨부 href 2개/KISTA DEXT5 설정 경로 3개를 추출합니다. KISTA 실제 download handler는 미검증이며, 저장/다운로드 기능이나 Notice 필드를 추가하지 않았습니다.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m tools.m16_smoke --source ripc_pms kista_ippro
```

원본 HTML 보정 후 전체 **442 tests OK**(기존 414개 + 신규 28개). 실제 smoke 재실행도 두 소스 모두 BLOCKED/DNS_ERROR/11001, exit 1입니다.
DNS 해소 후 RIPC AJAX 실제 응답/양 사이트 실제 2페이지 요청/최소 1건 HTTP 수집을 확인해야 합니다.
자세한 확인/미확인 범위와 재개 절차는 [M16 결과](docs/progress/M16_RESULT.md)를 참고합니다. M17 이후는 진행하지 않았습니다.

### M05 실제 HTML fixture 수집

Codex sandbox 밖 **일반 Windows PowerShell**에서 실행합니다. 외부 패키지 설치는 필요 없습니다.
아래 명령은 네트워크에 접속하여 M01에서 확인한 5개 사이트의 목록/표본 상세를 저장합니다.

```powershell
Set-Location 'D:\notice_crawling_new'
& 'C:\Users\이재혁\AppData\Local\Python\pythoncore-3.13-64\python.exe' .\tools\fetch_fixtures.py
```

저장 위치는 스크립트가 있는 프로젝트를 기준으로 다음과 같습니다.
각 디렉터리에 `list.html`, `detail.html`이 생성됩니다.

```text
tests/fixtures/khidi_business/
tests/fixtures/kised_bid_public/
tests/fixtures/rda_bid/
tests/fixtures/seoul_rnd_notice/
tests/fixtures/kipa_bid/
```

원본 응답 바이트를 그대로 저장하여 UTF-8/CP949 등 원래 문자 인코딩을 보존합니다.
기존 파일은 요청 전에 건너뜁니다. 파일 하나가 실패해도 나머지 목록/상세 다운로드는 계속합니다.
출력의 `SAVED`/`SKIPPED`/`FAILED`와 마지막 집계를 확인합니다.
실패가 하나라도 있으면 종료 코드 1, 모두 저장/건너뛰기면 0입니다.
HTTP 성공/HTML 형식 확인만 수행하므로 저장 후 실제 공고 페이지인지 확인해야 합니다.
이 도구는 selector, 사이트 scraper, 첨부파일 분석을 구현하지 않습니다.

필요할 때만 기존 파일을 덮어쓰거나 일부 사이트/timeout/User-Agent를 지정할 수 있습니다.

```powershell
& 'C:\Users\이재혁\AppData\Local\Python\pythoncore-3.13-64\python.exe' .\tools\fetch_fixtures.py --overwrite
& 'C:\Users\이재혁\AppData\Local\Python\pythoncore-3.13-64\python.exe' .\tools\fetch_fixtures.py --site khidi_business kipa_bid --timeout 45 --user-agent 'NoticeMonitor-FixtureFetcher/1.0'
```

URL은 `tools/fetch_fixtures.py`의 `TARGETS`에 모았습니다. 오래된 표본이 삭제된 경우 공식 목록에서 실제로 열리는 상세 URL로 갱신한 뒤 다시 실행합니다.

현재 상태는 `docs/progress/CURRENT_STATE.md`, 검증 근거는
`docs/progress/M16_RESULT.md`를 확인합니다. M16 실제 AJAX 응답/HTTP 검증과 별도로 M11 배포 URL 확인 → M12 실제 다운로드 검증도 남아 있습니다.
