# M10 Result

## Status

**PASS** — MILESTONES_V2.md M10 Central End-to-End Pipeline.

검증일: 2026-10-30 (Asia/Seoul). 오프라인 end-to-end와 전체 회귀 검증 및 인계를 완료했다.
실제 사이트/Gemini API를 통한 운영 성공을 의미하지 않는다.

## Implementation / Files

생성: src/pipeline.py, tests/test_pipeline.py, docs/progress/M10_RESULT.md.

수정: src/main.py, tests/test_smoke.py, README.md, docs/progress/CURRENT_STATE.md.

중앙 명령 흐름:

```text
site config load / clock 확정
→ 기존 Notice/status load 및 중복/손상/경로 충돌 검증
→ registry 실행 (기존 fetch/parse/normalize 재사용)
→ NEW / UPDATED / EXISTING diff
→ 중앙 Gemini 분석/캐시
→ 미관측 기존 기록을 포함한 전체 snapshot 병합
→ feed projection 사전 검증
→ Notice atomic save
→ public feed/metadata 생성
→ scraper status atomic save
```

저장소 검증은 외부 수집보다 먼저 수행한다. 손상 파일 때문에 나중에 저장할 수 없는 상황에서
외부 요청을 먼저 보내지 않도록 한 순서 조정이다. 기존 core/AI/feed/scraper 코드는 변경하지 않았다.

## Execution / Configuration

```powershell
.\.venv\Scripts\python.exe -m src.main
.\.venv\Scripts\python.exe -m src.main --help
```

선택 인자: --config, --data-dir, --public-dir. 기본 위치는 프로젝트 config/sites.yaml, data, public이다.
현재 기본 config의 enabled=false는 변경하지 않았다. 실제 실행 전 구현된 수집원을 명시적으로 활성화하고
GEMINI_API_KEY/GEMINI_MODEL을 프로세스 환경변수로 설정해야 한다. .env 자동 로딩은 없다.

실제 실행한 기본 명령 결과:

```text
CONFIGURATION ERROR: NO_ENABLED_SITES: enable an implemented source in sites.yaml
native exit code: 2
```

이는 사용자 요청에서 허용한 설정 오류 종료다. 실제 사이트/API 호출이나 운영 data/public 변경은 없다.
실행 종료 코드: 0=정상, 1=부분 실패 후 결과 저장, 2=설정/저장/diff/feed/기타 치명적 오류.
출력은 집계와 안전한 고정 오류 메시지이며 API key/원문 예외를 출력하지 않는다.

## Tests / Actual Results

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

**229 tests OK**, 실패/오류 0, exit code 0.
M10 신규 19개 + 기존 210개 통과(smoke의 예전 bootstrap 메시지는 현재 --help 계약으로 갱신).

테스트는 다섯 실제 M05 adapter와 사용자 HTML fixture에서 해당 상세 표본의 목록 행을 추출한 HTML,
fake Gemini, 임시 JsonStorage/public, 고정 clock을 사용한다. 네트워크 진입점은 금지 mock으로 막았다.
원본 fixture를 수정하거나 가짜 분석 결과를 운영 파일에 넣지 않았다.

| 시나리오 | 실제 검증 결과 |
| --- | --- |
| 첫 실행 | 5 NEW, Gemini 5회, 저장 5건, 관련 feed 5건, status 5개 SUCCESS |
| 두 번째 동일 실행 | 5 EXISTING, Gemini 추가 호출 0, 저장 5건 유지, feed notice data 동일 |
| 본문 1개 변경 | 1 UPDATED, Gemini 추가 1회, 새 hash 분석 저장, first_seen 유지 |
| 첫 실행 scraper 1개 실패 | 나머지 4개 수집/분석/저장/feed 완료 |
| 기존 데이터가 있는 scraper 1개 실패 | 실패 source 기존 Notice/분석/관측 시각 및 last_success 보존, 나머지 계속 |
| Gemini 일부 timeout/JSON 오류/irrelevant | 5건 저장, PENDING/FAILED 이력 유지, 관련 성공 2건만 feed |
| UPDATED 재분석 실패 | 이전 판단/hash 보존, 현재 분석은 PENDING, 다른 관련 4건 feed 유지 |
| 첫 빈 목록 | 빈 저장/빈 feed 생성, 성공 status count=0, Gemini 무호출 |
| 기존 기록이 있는 빈 목록 | 관측 0건, 기존 5건/관련 feed 보존, Gemini 추가 호출 0 |
| 모든 scraper 실패 | 전체 기존 snapshot/관련 feed 보존, ERROR status 기록 |
| 일부 비활성 | HTTP 무호출, 기존 기록/성공 시각 유지, WARNING/DISABLED 기록 |
| 손상 Notice/status, 중복 저장 ID | 수집 전에 명시적 오류, 자동 초기화/파일 덮어쓰기 없음 |
| public/data 경로 충돌 | 저장 파일을 덮어쓰기 전에 설정 오류 |
| feed writer 실패 | 이전 public 파일 보존(mock fault), 최신 Notice 저장 및 scraper status 저장 시도 |
| CLI | 비활성/키 누락 preflight 무호출, 정상/부분 실패 종료 코드 검증 |

## Preservation / Status Contract

- M07 batch는 관측 기록만 포함한다. 전체 이전 snapshot에 관측 ID만 덮어 병합하며 자동 만료/삭제하지 않는다.
- 미관측/실패/비활성 source의 Notice는 status/시각/Gemini 이력까지 그대로 보존한다.
- 병합 key는 stable notice_id이며 같은 실행 중복은 기존 M07 계약으로 처리한다.
  충돌 ID/손상 저장소는 전체 오류로 중단하고 임의 승자를 선택하지 않는다.
- 새 RelevanceAnalyzer를 실행마다 사용하고 저장된 성공 hash를 재사용한다. EXISTING은 API 무호출이다.
- FAILED/PENDING은 저장하되 public에서는 제외한다. UPDATED 실패 시 과거 판단을 최신 성공으로 배포하지 않는다.
- scraper 상태는 수집 성공 여부다. Gemini 분석 실패가 성공한 scraper 상태를 ERROR로 바꾸지 않는다.
- SUCCESS: 현재 attempt/success 시각, 고유 공고 수, 오류 필드 null.
- ERROR: 현재 attempt 시각, 이전 last_success, count=0, 안전한 error_type/실패 단계.
- WARNING/DISABLED: 시도하지 않았으므로 이전 attempt/success/count를 유지한다.
- 미등록 source의 기존 status도 유지한다. 개별 Gemini 오류 ID는 PipelineResult에 반환하고 분석 상태는 Notice에 저장한다.

## Programmatic Handoff

run_pipeline의 client/config_path/storage/public_dir/clock/transport_factory/logger를 주입할 수 있다.
실제 API 없이 전체 실행 가능하며 clock은 실행당 한 번 조회한다. ID/hash/본문 정규화는 기존 adapter/M03에 맡긴다.

반환 PipelineResult:

- notices: 전체 병합 snapshot tuple.
- observed: 이번 관측에 대한 diff/분석 후 Notice tuple.
- scraper_failures, analysis_failures: 이번 실행 오류 source/notice ID tuple.
- skipped: 비활성 등록 수집원 tuple.
- feed_count: 공개 대상으로 선택된 공고 수.
- degraded: 이번 scraper/분석 오류가 있으면 true.

## Limitations / Blocker

- M10 오프라인 구현 blocker 없음. 실운영에는 사이트 활성화/키/모델 설정 및 별도 네트워크 검증이 필요하다.
- JSON 문법 YAML만 읽으며 미구현 수집원 활성화/누락된 MVP/중복 config/잘못된 enabled는 오류다.
- 파일별 atomic write이며 전체 data/feed/status transaction이나 동시 writer 잠금은 없다.
  Notice 저장 후 feed 실패 시 최신 data와 이전/부분 public이 함께 남을 수 있다. 오류는 호출자에게 전파한다.
- feed write 실패에도 scraper status 저장을 시도한다. status까지 저장 실패하면 복구를 보장하지 않는다.
- 과거 미관측 공고는 영구 보존하며 종료일 기반 삭제/비공개 정책은 추가하지 않았다.
- FAILED/PENDING의 자동 재시도는 없다. 다음 실행에서 EXISTING이 되면 분석 호출하지 않는 M08 정책을 유지한다.
- analysis_failures 집계는 이번 시도의 오류다. 과거 실패 결과를 재사용한 모든 기록의 health 집계는 아니다.
- 기존 M05 표본/페이지 수집 및 M08 실제 모델 품질 검증 제한은 유지된다.
- Git/패키지 설치/외부 API/배포/로컬 클라이언트/회사 실적 로직 및 M11 이후는 수행하지 않았다.

## Acceptance / Next

- [x] 단일 src.main 명령으로 중앙 흐름 연결 및 명확한 설정 오류.
- [x] 실제 fixture/fake Gemini/임시 저장소의 오프라인 E2E.
- [x] 반복 실행 안정성/EXISTING 무호출/본문 변경 재분석.
- [x] 사이트·Gemini 부분 실패 격리 및 기존 데이터 보존.
- [x] 관련 feed 및 scraper status 저장.
- [x] 전체 unittest/실환경 설정 오류 실행/결과 문서/인계.

다음은 **V2 M11 — GitHub Repository / Daily Automation / JSON 배포**다.
이번에는 GitHub 연결/Actions/Pages 작업을 진행하지 않았다.
