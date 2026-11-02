# M16.1 — Windows executable packaging

## Status

**M16.1 PASS — 일반 PowerShell 빌드/실제 exe 실행/Tk UI 표시 성공.**
2026-11-02. 사용자가 제공한 외부 실측 결과와 기존 회귀/Tk smoke를 근거로 요청에 따라 PASS로 갱신했다.
사용자 보고: PyInstaller 설치 성공, build_windows.ps1 성공, exe 생성 및 실제 실행 성공, Tk UI 정상 표시.
M16 수집 PASS는 그대로 유지한다. 이번 변경은 문서만 갱신했으며 코드/기능/계약 변경과 M17 진행은 없다.

## 확인 범위 / 구현 파일

UI 진입점과 참조 local_client, requirements, config의 M16 상태, 기존 UI smoke, 경로 참조만 확인했다.
UI는 stdlib Tkinter/dashboard/matcher/performance/sync만 사용하며 config/sites.yaml이나 별도 static/resource를 읽지 않는다.

- tools/windows_entry.py: 기존 src.local_client.ui.main을 호출하는 packaging adapter.
- build_windows.ps1: 프로젝트 .venv에만 빌드 도구 설치, onedir/windowed 빌드, 앱 산출물 경로 검증·정리, 실행 안내 복사.
- requirements-build.txt: PyInstaller==6.22.3. 기존 runtime requirements는 변경하지 않음.
- tools/windows_README.txt: 배포 폴더용 실행 안내.
- tests/test_windows_packaging.py: frozen 경로/명시적 옵션/개발 실행/쓰기 없음 4개 테스트.
- README.md: 필요한 빌드/실행/데이터 위치 안내만 추가.

기존 UI/matcher/scraper/DB/cache/feed/schema 코드 및 M16 상태는 변경하지 않았다.

## 배포 구성 / 경로

생성된 exe: D:\notice_crawling_new\dist\notice_crawling\notice_crawling.exe (사용자 제공 실제 빌드 결과).
배포 폴더는 dist/notice_crawling이며 exe/_internal/README.txt를 함께 전달한다. onefile은 만들지 않는다.
빌드 옵션: --onedir --windowed --name notice_crawling --noupx --contents-directory _internal.
PyInstaller의 Tk/Python/SQLite runtime 수집을 사용한다. 외부 실측에서 exe 실행과 Tk UI 표시 성공을 확인했다.

UI에 필요하지 않은 config/sites.yaml, 중앙 scraper, 소스 트리/테스트/개발 문서/fixture/개인 DB/cache는 add-data로 포함하지 않는다.
Python 코드는 분석된 필요한 모듈의 컴파일 번들로 배포하며 소스 트리를 복사하지 않는다.

exe 기본 데이터 위치는 %LOCALAPPDATA%/NoticeCrawling/cache/snapshot.json 및 performance.db다.
LOCALAPPDATA가 없으면 사용자 홈의 AppData/Local/NoticeCrawling을 사용한다.
기존 --cache/--db 인자가 우선하며 상대 경로는 호출 CWD 기준인 기존 의미를 유지한다.
UI의 기존 파일 경로 입력란도 유지한다. 데이터 경로 생성/DB 초기화/cache 다운로드는 하지 않는다.
개발 PC 절대 경로와 _MEIPASS에 사용자 파일을 두지 않는다. 별도 UI 리소스가 없어 _MEIPASS resource helper도 추가하지 않았다.

## 실제 검증 결과

- PowerShell AST 문법 검사: OK.
- 최종 외부 실측(사용자 제공): 일반 PowerShell에서 PyInstaller 설치 및 build_windows.ps1 실행 성공.
- 최종 외부 exe smoke(사용자 제공): 위 exe 실제 실행 성공, Tk UI 정상 표시.
- Codex 내부 이력: pip 설치는 PyPI DNS_ERROR/11001, script 실행은 AuthorizationManager/UnauthorizedAccess였다. 이는 해당 실행환경 제한이며 외부 빌드/실행 성공과 구분한다. 실행 정책/보안 설정을 변경하거나 우회하지 않음.
- 전체 unittest: **Ran 446 tests / OK / 71.348s / exit 0**. 기존 442개 + packaging 4개.
- 기존 tests/ui_dashboard_smoke.py: **UI_SMOKE_PASS**, 실제 Tk widget/선택/점수/근거/TOP N/입력 무효화/빈 결과/읽기 전용 입력 검증.
- 위 자동 Tk smoke는 기존 Python 소스 실행이다. exe 실행/Tk 표시 성공은 별도의 사용자 제공 외부 실측 근거다. exe에서 DB/cache 로딩·매칭·한글·정상 종료 각각의 상세 결과는 이번 보고에 없으므로 별도 확인 완료로 표시하지 않는다.
- 개인 데이터: build script는 소스/fixture/DB/cache를 add-data로 포함하지 않는다. 최종 배포 폴더 내용의 독립 감사 결과는 제공되지 않았으며 감사 완료로 표시하지 않는다.
- exe 네트워크 smoke: 미수행. 기존 UI는 오프라인 프로그램이며 중앙 scraper를 추가 번들하거나 exe에 새 수집 기능을 넣지 않음.

## 재현 / 추가 관찰 사항 / Blocker

일반 PowerShell의 프로젝트 루트에서 ./build_windows.ps1을 실행한다.
스크립트가 requirements-build.txt를 프로젝트 .venv에 설치한다. 사용자 제공 일반 PowerShell 결과로 설치/빌드/실행 blocker는 해소했다.
Codex 내부 DNS/스크립트 실행 제한은 환경 이력으로 남기며 M16.1 종료 blocker로 취급하지 않는다.
스크립트는 해당 앱의 build/notice_crawling, build/windows_spec, dist/notice_crawling만 정리한다.
절대 경로/프로젝트 하위 여부 및 junction/symlink ancestor를 검증한 뒤 정리하며 local 사용자 데이터는 건드리지 않는다.

실행 방법: dist/notice_crawling/notice_crawling.exe 더블클릭. 사용자 PC에 Python/venv를 별도로 설치할 필요가 없다.
추가 관찰 사항: 다른 경로/PC에서 실행, 외부 DB/cache 로딩 및 exe 안의 상세 매칭 조작, 최종 번들 내용 감사. 제공된 외부 실측 이상의 검증을 주장하지 않는다.
사용자 지정 외부 빌드/실행/Tk 정상 결과와 기존 446개 회귀/소스 Tk smoke를 근거로 M16.1 PASS 종료했다. 종료 blocker 없음.
M17은 사용자 요청 없이 진행하지 않는다.
