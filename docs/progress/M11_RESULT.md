# M11 Result

## Status

**PARTIAL** — 코드/워크플로/문서 및 오프라인 검증 완료. 실제 GitHub 실행/Pages 공개 URL 검증은 미완료다.

재검증일: 2026-11-02 (Asia/Seoul). MILESTONES_V2.md M11 범위만 수행했다.
기존 M11 구현을 확인하고 배포 URL 기록, 안전한 오류 분류, 회귀 테스트를 보완했다.
M00~M10 계약을 유지했으며 M12 이후는 구현하지 않았다.

## Implementation / Files

- `.github/workflows/central-notice-pages.yml`: daily/dispatch, state 복원, 중앙 pipeline, JSON pair 검증, Pages 배포 및 실제 feed URL 로그/Summary.
- `tools/actions_support.py`: 설정 검사, 저장 snapshot/public 일치 검증, 두 JSON만 staging, 안전한 상태 진단. 손상 상태는 고정된 예외 분류만 출력한다.
- `tests/test_actions_support.py`: 오프라인 helper/워크플로 계약 테스트 20개.
- `tests/test_actions_state_selector.cjs`: 실제 workflow JavaScript를 fake API로 실행하는 선택 로직 테스트 6개(Node 내장 모듈만 사용).
- `docs/operations/GITHUB_PAGES.md`: 최소 활성 설정, Secret/Variable/Pages/최초 실행 및 복구 절차.
- `docs/progress/CURRENT_STATE.md`: 현재 검증/운영 blocker 갱신.

기존 README의 운영 문서 링크와 .gitignore의 임시 산출물/credential 제외를 유지했다.
src/main.py, src/pipeline.py, public feed/core/AI/scraper 및 운영 config/data/public은 변경하지 않았다.
외부 Python 패키지/framework 설치나 실제 secret/credential 저장은 하지 않았다.

## Workflow Contract

1. 매일 22:17 UTC(다음 날 07:17 KST) 및 workflow_dispatch. 기본 브랜치만 실행한다.
2. ubuntu-latest / Python 3.13 / pip 설치 없이 전체 unittest와 설정 preflight를 실행한다.
3. GEMINI_API_KEY는 repository Actions Secret, GEMINI_MODEL은 repository Actions Variable에서 필요한 두 step에만 env로 전달한다.
4. 이전 central-state-v1 artifact의 Notice/status를 복원·검증한다. hosted runner 간 Gemini hash 캐시/first_seen을 유지한다.
5. `python -m src.main --data-dir .run/data --public-dir .run/public`으로 기존 중앙 pipeline을 실행한다.
6. 저장 snapshot으로 M09 projection을 재계산해 schema/count/시각/내용 일치를 검사한다.
7. .run/pages에는 notices.json/metadata.json 두 개만 생성해 공식 Pages Actions로 배포한다.
8. 배포 성공 후 실제 page_url 기반 두 JSON URL을 로그/Summary에 기록한다. 실제 HTTP 접근은 별도 확인 사항이다.

concurrency는 전체 실행을 직렬화하며 진행 중 취소하지 않는다.
state 부재는 최초 수동 bootstrap_state=true에서만 허용한다. 만료/손상은 자동 초기화하지 않는다.
M10 exit 1은 PARTIAL warning 후 유효한 결과를 배포하고, exit 2 이상/검증 실패는 배포를 막는다.
원본 data/state/진단은 Pages artifact에 포함하지 않는다. deploy job만 Pages write/ID-token write를 가진다.
첫 실패 step, pipeline 종료 코드, 안전한 diagnostics 로그/Summary/artifact로 원인을 확인한다.

## Tests / Actual Results

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test tests/test_actions_state_selector.cjs
.\.venv\Scripts\python.exe -m json.tool .github/workflows/central-notice-pages.yml > $null
```

- 전체 **249 unittest OK**, 실패/오류 0, exit code 0 (기존 244 + 이번 보완 5).
- 별도 Node selector **6 tests PASS**, exit code 0. 기존 로컬 Node만 사용하며 Python/Actions unittest의 필수 의존성으로 추가하지 않았다.
- JSON 문법 YAML 1.2 파싱 및 schedule/dispatch/Python/권한/Secret scope/복원 순서/배포 경로/실제 URL 기록 구조 확인.
- 신규 회귀: 손상 상태 배포 차단/파일 보존, 중복 ID 차단, 임의 예외 이름·내용 비노출, CLI 임시 경로/네트워크 금지, 실제 배포 URL 연결.
- selector: 최초 부재 실패/bootstrap, 최신 선택, 다른 브랜치·저장소 제외, 만료 시 fallback/bootstrap 금지, 기존 상태 우선 복원.

외부 사이트/Gemini API/GitHub 실행 없이 검증했다. 실제 Actions expression/server validator/Linux runner/Pages HTTP 배포는 미검증이다.
PyYAML/actionlint는 설치하지 않았다. JSON 구조 검증을 실제 GitHub 실행 성공으로 간주하지 않는다.

## Manual GitHub Setup / Handoff

정확한 절차: [GITHUB_PAGES.md](../operations/GITHUB_PAGES.md).

1. 현재 프로젝트 파일을 대상 저장소 기본 브랜치 루트에 반영한다. .venv/.env/credential/임시 산출물은 제외한다.
2. repository Actions Secret GEMINI_API_KEY와 Variable GEMINI_MODEL을 설정한다.
3. 현재 전부 false인 config/sites.yaml에서 구현 source 하나 이상만 enabled=true로 변경한다.
   구현 ID: khidi_business/kised_bid_public/rda_bid/seoul_rnd_notice/kipa_bid. 전체 inventory를 유지한다.
4. Pages Source=GitHub Actions, 공식 Actions 및 github-pages environment의 기본 브랜치 배포를 허용한다.
5. 최초 수동 실행에만 bootstrap_state=true. pipeline exit 0 및 Gemini SUCCESS를 확인한다.
6. 배포 Summary의 두 JSON URL을 로그아웃 상태에서도 열어 공개 접근/시각/count 일치를 확인한다.

## Blockers / Limitations

- 현재 작업 폴더에는 .git이 없고 Git 명령은 not a git repository로 종료됐다. 원격 연결/업로드는 이번에 수행하지 않았다.
- 이전 문서의 대상은 Emoty-9s/notice_crawling(main/private)이다. 이번에는 원격 상태/권한/설정을 재확인하지 않았다.
- 이전 .run/M11_UPLOAD.zip/manifest는 이번 수정 전 산출물일 수 있다. 이번 반영본 대신 사용하지 않는다.
- Secret/Variable/사이트 활성화/Pages 설정, 실제 수동 실행 및 두 공개 URL 확인이 남아 있다. 공개 URL은 아직 확정되지 않았다.
- private 저장소의 Pages 지원 플랜은 운영자가 확인해야 한다. visibility는 임의로 변경하지 않는다.
- state artifact는 90일 보존 요청이며 조직 정책/삭제/장기 중단 시 백업 복구가 필요하다.
- pipeline/state/Pages 전체 transaction은 없다. 부분 실패 run은 green일 수 있으므로 Summary를 확인한다.
- M08 실패 재시도 정책과 M10 데이터 보존/파일별 atomic write 계약은 그대로다.

## References / Next

공식 참조 확인: [checkout](https://github.com/actions/checkout), [setup-python](https://github.com/actions/setup-python),
[github-script](https://github.com/actions/github-script), [download-artifact](https://github.com/actions/download-artifact),
[upload-artifact](https://github.com/actions/upload-artifact). 단일 artifact ID는 지정 경로에 바로 복원하는 공식 동작을 확인했다.

다음: 실제 GitHub 설정 → 최초 dispatch → 두 JSON 공개 접근 및 후속 실행 상태 복원 확인으로 M11을 마무리한다.
M12는 사용자 요청 전 착수하지 않는다.
