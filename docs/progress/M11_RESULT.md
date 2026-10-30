# M11 Result

## Status

**PARTIAL** — 대상 저장소 확정/접근 확인 및 업로드 준비 완료. 실제 업로드/설정/수동 실행/배포 URL 검증 미완료.

검증일: 2026-10-30 (Asia/Seoul). MILESTONES_V2.md M11만 수행했다.
대상: https://github.com/Emoty-9s/notice_crawling (private, 기본 브랜치 main).
GitHub connector의 get_repo로 저장소 ID 1439083905, 관리자/push 권한 및 비어 있는 상태(size=0)를 확인했다.
로컬 Git remote 추가/commit/push는 수행하지 않았다. 저장소 visibility도 변경하지 않았다.

## Implementation / Files

생성:

- .github/workflows/central-notice-pages.yml
- tools/actions_support.py
- tests/test_actions_support.py
- docs/operations/GITHUB_PAGES.md
- docs/progress/M11_RESULT.md

수정: .gitignore(.run/안전한 진단 산출물 제외), README.md(설정 안내 링크), docs/progress/CURRENT_STATE.md.

src/main.py, src/pipeline.py, core/AI/scraper/feed 및 실제 config/data/public은 변경하지 않았다.
외부 Python 패키지/framework를 추가하거나 설치하지 않았다. requirements.txt는 기존 표준 라이브러리 계약 그대로다.
실제 secret/credential 생성/출력/파일 저장/Git 명령/외부 저장소 쓰기는 수행하지 않았다.

## Workflow Contract

- 매일 22:17 UTC=07:17 KST 및 workflow_dispatch. 기본 브랜치에서만 실행한다.
- ubuntu-latest / Python 3.13 / pip 설치 없이 전체 unittest → 설정 preflight → state 복원/검증 → M10 pipeline.
- GEMINI_API_KEY는 repository Actions Secret, GEMINI_MODEL은 repository Actions Variable에서 env로 주입한다.
- hosted runner 간 state는 central-state-v1 artifact(90일 요청)로 전달한다. 이전 Notice/Gemini hash 캐시를 유지한다.
- state가 없으면 실패하며 최초 수동 bootstrap_state=true에서만 빈 시작을 허용한다. 만료/손상은 자동 reset하지 않는다.
- concurrency는 실행 전체를 직렬화하고 진행 중 실행을 취소하지 않는다.
- pipeline exit 1은 warning/PARTIAL 집계와 함께 검증된 저장/feed를 보관·배포한다. 2 이상은 배포하지 않는다.
- 저장 snapshot과 public JSON의 정확한 일치/count/schema/시각을 검사한 후 JSON 두 개만 별도 staging에 생성한다.
- 공식 upload-pages-artifact/configure-pages/deploy-pages를 사용한다. deploy job만 Pages write/ID-token write를 가진다.
- 원본 data/state/secret/진단은 Pages artifact에 넣지 않는다. safe diagnostics를 항상 시도하며 로그/Summary/artifact로 제공한다.
- JSON 문법 YAML 1.2를 사용해 추가 parser 없이 로컬 구조 검사 가능하게 했다.

## Tests / Actual Results

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

**244 tests OK**, 실패/오류 0, exit code 0. 신규 15개 + 기존 229개 통과.
네트워크/API/GitHub 없이 실행했다.

신규 테스트: 활성 설정/Secret 이름·유효성/비활성 preflight, state completeness,
빈·정상 snapshot staging, metadata count/시각/type 오류, 오래된·내부 필드가 추가된 feed 거부,
오염된 stage 재사용 금지, 진단의 본문/원문 오류/키 미출력,
workflow schedule/dispatch/default branch/concurrency/Python/permissions/restore 순서/Pages 경로 검사.

별도 로컬 Node mock 검증: **state selector 6개 시나리오 PASS**.
artifact 없음 → 오류, 최초 bootstrap 허용, 최신 ID 선택, 타 브랜치/저장소 제외,
최신 artifact 만료 시 이전 것으로 조용히 후퇴하지 않음, bootstrap으로 만료 우회 금지를 검증했다.
workflow 내 JavaScript는 AsyncFunction으로 실제 파싱·실행했으며 GitHub API 객체만 fake로 주입했다.
Node는 현재 환경에 이미 있어 사용했으며 설치/런타임 의존성을 추가하지 않았다.

workflow 파일은 Python json parser로 파싱되고 단위 테스트가 구조/계약을 검사한다.
실제 GitHub workflow schema/expression/action 실행 및 Linux runner는 미검증이다.
PyYAML/actionlint는 환경에 없으며 새 패키지를 설치하지 않았다.

## Manual GitHub Setup / Handoff

정확한 설정/URL 확인/오류 복구 절차: [GITHUB_PAGES.md](../operations/GITHUB_PAGES.md).

1. 저장소 선택/생성 및 기본 브랜치에 파일 반영.
2. GEMINI_API_KEY Secret / GEMINI_MODEL Variable 설정.
3. config/sites.yaml에서 구현된 수집원 하나 이상 enabled=true로 변경(나머지 47개 coverage 유지).
4. Pages Source=GitHub Actions, workflow 권한 및 github-pages environment 허용.
5. 첫 수동 실행에만 bootstrap_state=true. 이후 정상 기본값 false.
6. 수동 실행 성공 후 실제 deployment URL의 notices.json/metadata.json 접근 및 count/시각 확인.

현재 config는 계속 전부 false다. 미구현 수집원을 자동 활성화하지 않았다.
추가 PAT/개인 credential은 필요 없고 자동 GITHUB_TOKEN을 Actions가 공급한다.

## Acceptance / Blockers

- [x] daily/수동 workflow 및 Secret 참조 구현.
- [x] pipeline/상태 복원/검증/public JSON Pages 배포 단계 구현.
- [x] 최소 Python 환경/외부 패키지 없음/안전한 단계 로그·진단.
- [x] 기존 M00~M10 계약 보존 및 전체 unittest.
- [x] 대상 저장소 확정 및 GitHub connector 접근/권한/private 상태 확인.
- [ ] 로컬 파일 업로드 및 GitHub 설정 — 사용자 수동 반영 필요.
- [ ] 실제 Secret 사용/수동 workflow 성공 — Secret/Variable/사이트 활성화/권한/Pages 설정 필요.
- [ ] 실제 public JSON 두 URL 및 반복 원격 접근 — deployment URL 미확보.

운영 제한: artifact retention/삭제에 따른 상태 유실은 운영 백업/복구가 필요하다.
raw state artifact는 repository 읽기 권한자가 접근할 수 있으며 공개 저장소에서는 공개될 수 있다.
서로 다른 파일/배포 전체 transaction은 제공하지 않는다. 부분 실패는 warning이므로 Actions run이 green이어도 Summary를 확인한다.
기존 M08 실패 재시도/캐시 정책과 M10 데이터 보존 계약은 변경하지 않았다.

## Sources / Next

Pages action/권한은 [GitHub 공식 custom workflow 문서](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)를 확인했고,
artifact 복원 방식은 [공식 download-artifact 문서](https://github.com/actions/download-artifact)를 확인했다.
일일 트리거/권한/순서는 [workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)를 기준으로 작성했다.

다음: 실제 GitHub 설정 및 수동 실행/두 public URL 검증으로 M11을 마무리한다.
그 후 사용자 요청 시 V2 M12를 진행한다. 이번에 로컬 클라이언트/실적 DB/매칭을 구현하지 않았다.

## Confirmed Repository / Push Preparation / Manual Stop

확정 repository: **Emoty-9s/notice_crawling**, main, private 유지.
접근 가능한 저장소를 확인한 것과 로컬 Git remote/원격 파일 반영은 구분한다. 원격 파일은 아직 업로드하지 않았다.

업로드 준비물:

- `.run/M11_UPLOAD.zip`: 코드/테스트/실제 HTML fixture/workflow/config/문서. 압축 내부는 repository root 기준이다.
- `.run/M11_PUSH_MANIFEST.json`: 대상 repository/branch/private 및 파일 경로/크기/SHA-256 목록.
- .venv/.git/.env/credentials/secrets/실제 key/원본 XLSB/임시 산출물은 포함하지 않는다.
  `.env.example`은 값 없는 템플릿만 포함한다. 준비물은 .gitignore의 .run 아래에 있으며 자동 업로드되지 않는다.

현재 GitHub connector에는 Secret/Variable/Pages 설정 및 최초 workflow_dispatch 기능이 없다.
이전 UI 시도는 Windows 브라우저의 현재 URL을 검증할 수 없어 도구가 중단했다.
사용자의 최신 지시에 따라 UI 조작을 재시도하거나 unrelated 설정을 바꾸지 않고 아래 수동 작업을 남기고 중단한다.

사용자가 할 정확한 순서:

1. `.run/M11_UPLOAD.zip`을 풀고 [대상 repository](https://github.com/Emoty-9s/notice_crawling)의 main에 **압축을 푼 파일/폴더**를 반영한다.
   ZIP 자체를 repository 파일로 올리는 것이 아니다. `.github/workflows/central-notice-pages.yml`, src, tests/fixtures가 루트 기준 경로에 있어야 한다.
   visibility는 **private**로 유지한다.
2. [Actions Secrets](https://github.com/Emoty-9s/notice_crawling/settings/secrets/actions)에서 repository secret `GEMINI_API_KEY`의 등록 여부를 확인한다.
   없다면 GitHub 입력란에 직접 등록한다. 채팅/코드/로그/업로드 파일에 key 값을 넣지 않는다.
3. [Actions Variables](https://github.com/Emoty-9s/notice_crawling/settings/variables/actions)에 repository variable `GEMINI_MODEL`을 등록한다.
   해당 키에서 구조화 JSON 출력을 사용할 수 있는 명시적 모델 ID를 입력한다. 다른 필수 model/config Variable은 없다.
4. main의 config/sites.yaml에서 구현된 5개 중 실제 수집할 source 하나 이상의 enabled를 true로 변경한다.
   khidi_business/kised_bid_public/rda_bid/seoul_rnd_notice/kipa_bid만 구현돼 있다. 나머지 source는 false 유지한다.
   업로드 준비물은 기존 설정 계약을 보존하여 모두 false다.
5. [Pages 설정](https://github.com/Emoty-9s/notice_crawling/settings/pages)의 Source를 GitHub Actions로 지정한다.
   private 저장소 Pages는 이를 지원하는 플랜이 필요하다. 메뉴에서 업그레이드를 요구하면 **public으로 바꾸지 말고 중단**한다.
   [GitHub 공식 안내](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)에 private Pages 지원 조건이 명시돼 있다.
6. Settings → Actions에서 workflow/공식 Actions 사용을 허용하고 github-pages environment가 main 배포를 허용하는지 확인한다.
7. [Workflow](https://github.com/Emoty-9s/notice_crawling/actions/workflows/central-notice-pages.yml) → Run workflow → main → 최초에만 bootstrap_state=true로 실행한다.
8. build/deploy 성공 및 pipeline exit 0, 진단의 분석 SUCCESS를 확인한다. exit 1 경고만 있는 green run을 Gemini 정상 사용 확인으로 간주하지 않는다.
   실패하면 실제 step/job 로그에서 첫 오류를 확인한다. 현재 실행하지 않았으므로 추측에 의한 코드 수정은 하지 않았다.
9. deploy가 표시한 실제 page_url 뒤의 `/notices.json`, `/metadata.json`을 각각 로그아웃 상태에서도 열어 접근/생성 시각/count 일치를 확인한다.
   `https://emoty-9s.github.io/notice_crawling/`는 예상 기본 경로일 뿐 현재 확인된 공개 URL이 아니다.

수동 실행/Secret 정상 사용/두 URL이 확인되기 전까지 M11은 PARTIAL이다. M12는 시작하지 않았다.
