# 사업공고 모니터링 시스템

공고 사이트의 신규/수정 공고를 수집하고, Gemini가 특허법인/특허사무소의
수행 주체 참여 가능성을 판정하여 공통 JSON으로 제공합니다.
현재 개발 범위는 `MILESTONES_V2.md`를 따릅니다. 회사 실적 매칭은 이후 로컬 영역입니다.

현재 구현은 **M10 — Central End-to-End Pipeline**입니다.
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
다른 사이트를 활성화하면 설정 오류로 종료합니다. 기본 config의 enabled 값은 변경하지 않았습니다.

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

## 인계

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
`docs/progress/M11_RESULT.md`를 확인합니다. 다음 작업은 실제 GitHub에서 M11 배포 검증입니다.
