# M15 Result

## Status

**PASS — 이번 요청의 오프라인·읽기 전용 M15 UI 범위.**
검증일: 2026-11-02 (Asia/Seoul). 실제 전체 unittest와 Tk 위젯 smoke 결과를 확인한 뒤 기록했다.
기존 M14 알고리즘을 UI에서 그대로 호출하며 M16 이후 작업은 수행하지 않았다.

## 구현 목적 / 범위

사용자가 로컬 공고를 선택하고 기존 M14 TOP N/총점/규칙별 근거를 확인하는 데스크톱 UI다.
MILESTONES_V2.md가 허용한 간단한 데스크톱 방식 중 stdlib Tkinter를 선택했다.
프로젝트에 기존 UI나 외부 의존성이 없어 프레임워크/웹 서버/브라우저/패키지를 추가하지 않았다.

원래 M15 문서의 온라인 feed 업데이트/원문 열기/실원격 다운로드는 이번 요청의 통신 금지 및 M11/M12 제외 지시에 따라 수행하지 않는다.
UI의 업데이트는 로컬 파일 다시 읽기이며 URL은 텍스트 표시만 한다.
현재 feed에는 NEW/UPDATED 상태가 없으므로 이를 새로 추론하거나 schema에 추가하지 않았다.
몇 주간의 실사용 Gate를 완료했다고 주장하지 않는다. 비식별 피드백 기록 구조를 제공했다.

## 구현 파일

- src/local_client/dashboard.py: 읽기 전용 데이터 loader, 표시용 presenter, 상세 텍스트.
- src/local_client/ui.py: Tkinter 공고 목록/선택/입력/추천/근거 화면 및 독립 실행 진입점.
- tests/test_dashboard.py: display가 필요 없는 M15 전용 unittest 24개.
- tests/ui_dashboard_smoke.py: 실제 Tk widget smoke(전체 unittest와 별도 실행).
- docs/usage/ISSUES.md, docs/usage/IMPROVEMENTS.md: 비식별 실사용 기록 템플릿.
- README.md, docs/progress/CURRENT_STATE.md: 실행 방법/최신 상태 갱신.
- docs/progress/M15_RESULT.md: 범위/계약/검증/인계.

## UI 구조 / 사용 방법

```powershell
.\.venv\Scripts\python.exe -m src.local_client.ui
.\.venv\Scripts\python.exe -m src.local_client.ui --cache '.\local\cache\snapshot.json' --db '.\local\performance.db' --reference-year 2026 --top-n 5
.\.venv\Scripts\python.exe -m src.local_client.ui --help
```

기본 cache는 기존 local/cache/snapshot.json, DB는 local/performance.db다. 파일이 없으면 상태 오류를 표시하며 생성하지 않는다.
화면 상단에서 기존 파일 경로를 입력하고 **파일 다시 읽기 → 공고 선택 → 기준 연도 입력 → 매칭 실행 → 추천 실적 선택** 순서로 사용한다.
원격 URL이나 API key는 UI 설정에 필요 없다. 유효한 기존 로컬 파일을 사용한다.

상단에는 입력 경로, cache 생성 시각/검증 상태/공고·실적 수, 기관·category·텍스트 필터를 표시한다.
왼쪽에는 공고 목록과 선택 공고 상세, 오른쪽에는 추천 실적 목록과 선택 실적의 점수 근거를 표시한다.
원문 URL/기존 선별 근거는 feed의 텍스트를 표시하며 브라우저나 AI를 호출하지 않는다.
텍스트 상세 widget은 읽기 전용이다. 입력 문구를 HTML/코드로 실행하지 않는다.

TOP N은 기본 5이며 0 이상의 정수를 입력할 수 있다. 기준 연도는 빈 값으로 시작하고 사용자가 직접 입력하거나 CLI로 지정한다.
현재 날짜/연도를 자동 조회하거나 저장된 공고 날짜를 기준 연도로 추론하지 않는다.
경로 변경 시 로드 데이터와 결과를 모두 무효화한다. 공고/필터/연도/TOP N 변경 시 이전 추천을 지워 조건이 섞이지 않게 한다.
잘못된 입력/없는 파일/손상 schema/빈 공고/빈 실적/TOP N=0을 상태 메시지로 처리한다.

## Matcher 연계 방식 / 사용자 확인 항목

recommendation_rows는 기존 공개 함수 matcher.match_notice(notice, performances, reference_year=..., top_n=...)만 호출한다.
UI는 가중치/category 관계/정규화/점수/정렬/동점 정책을 수정하지 않는다.
반환 MatchResult.to_dict()에 같은 읽기 snapshot의 project_name과 표시 순번을 결합한다.
총점은 matcher의 score 그대로다. 규칙 합계를 별도로 더해 일치 여부를 표시하며, 불일치도 숨기거나 점수를 보정하지 않는다.

| 영역 | 표시 항목 |
| --- | --- |
| 공고 | notice_id, title, institution, category, participation_type, keywords, summary, relevance_reason, url |
| 추천 | ranking, performance_id, project_name, total_score |
| 근거 | 규칙 원래 이름 및 한글 이름, 규칙별 points, terms, matched_terms, 규칙 합계, 총점과 합계의 일치 여부 |

예시 합성 데이터에서는 기존 M14와 동일한 22점과 technical_field/work_type/keyword/category/title/recent 근거를 표시했다.
0점 실적은 기존 matcher 계약대로 표시하며 적용된 가점 규칙이 없다는 것을 명시한다.

## 원본 보호 / 외부 통신 여부

- cache는 파일 읽기와 기존 M12 validate_pair 공개 검증만 수행한다. FeedClient 생성은 출처 형식 검증에만 사용하며 sync/download/save를 호출하지 않는다.
- DB는 SQLite URI **mode=ro** 및 query_only로 연다. 기존 DB 버전/컬럼 및 공개 Performance 모델로 검증하고 전체 실적을 읽는다.
- UI에서는 PerformanceStore 생성자를 호출하지 않는다. 누락 DB 생성/schema 초기화/write lock을 유발하는 초기화 경로를 사용하지 않는다.
- DB/schema/CSV/cache 저장 함수를 호출하지 않는다. 매칭/필터/선택 결과는 메모리에만 있다.
- 네트워크/socket 연결, HTTP 서버, 외부 API, Gemini, embeddings, 크롤링, 브라우저 실행, 실적 업로드 없음.
- 고객명/client, attorneys, notes는 추천 표시 payload에 포함하지 않는다. 오류 메시지도 고정 코드만 표시한다.

## 변경하지 않은 계약

M14 matcher.py/점수 공식/가중치/공개 API, M13 performance.py/DB schema/CRUD/CSV,
M12 sync.py/CLI/feed/cache schema, 중앙 pipeline/AI/공개 feed/Actions는 변경하지 않았다.
기존 테스트 파일과 328개 테스트도 유지했다. 새로운 파일과 README/진행·사용 문서만 추가/갱신했다.

## 테스트 항목 / 실제 결과

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_dashboard.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tests/ui_dashboard_smoke.py
.\.venv\Scripts\python.exe -m src.local_client.ui --help
```

- **신규 24 unittest OK. 전체 352 unittest OK**(기존 328 + 신규 24), 실패/오류 0, exit code 0.
- 실제 Windows/Python 3.13/Tk 8.6에서 별도 **UI_SMOKE_PASS**, exit code 0. Tk root는 숨긴 상태로 실제 widget/event 흐름을 검증했다.
- 모듈 --help도 exit code 0. headless 전체 unittest에서는 Tk root를 만들지 않아 display/GUI 패키지 설치가 필요 없다.

unittest 검증: 필수 공고 정보·한글 표시, 공개 matcher 호출 및 명시적 입력 전달, TOP N,
순위/과제명/총점, 모든 rule/points/evidence 표시, 점수 합계와 불일치 표시,
빈 DB/feed/선택/잘못된 연도·TOP N, 동일 입력·동일 상세 텍스트, 기관/category/검색,
입력 불변, DB/cache bytes 불변, mode=ro 및 DML 미실행, 누락 파일 미생성,
손상 DB/schema/cache를 빈 성공으로 숨기지 않음, 개인정보 필드 미복사, 텍스트 비실행, --help.
HTTP/socket 연결/Gemini/FeedClient.sync/PerformanceStore 초기화를 금지 mock으로 막은 상태에서 테스트했다.

실제 widget smoke 검증: 목록 2건, 연도 자동 기본값 없음, 미입력 오류, 공고 선택 → 22점/규칙 표시,
TOP N 변경 시 이전 결과 제거, TOP 1/TOP 0, 경로 변경 시 이전 데이터 제거, 누락 파일 오류,
읽기 전용 상세 text, DB/cache 전후 bytes 동일 및 임시 파일 정리.

## Blocker / 한계

이번 M15 구현 blocker 없음. Tk가 포함된 Python과 로컬 데스크톱 세션이 필요하며 현재 환경에서 확인했다.
화면은 로드 시점의 로컬 snapshot을 사용한다. 외부에서 파일이 변경되면 사용자가 파일 다시 읽기를 눌러 반영한다.
전체 실적을 메모리에 읽어 기존 matcher를 동기 호출한다. 대규모 데이터의 응답성 최적화는 추가하지 않았다.
실제 사용자 데이터/장기간 실사용/모든 화면 배율의 시각 검수는 이번 합성 데이터 검증에 포함하지 않았다.

## 남은 별도 작업

- M11 배포 URL 확인.
- 그 이후 M12 실제 GitHub HTTP 다운로드 검증.

위 작업은 이번에 수행하지 않았으며 M15 PASS가 이 작업의 완료를 의미하지 않는다.

## Next

사용자가 기존 로컬 파일로 UI를 실행해 추천 근거를 확인하고 docs/usage에 비식별 피드백을 기록할 수 있다.
M16 이후 또는 다른 기능은 요청 없이 진행하지 않는다.
