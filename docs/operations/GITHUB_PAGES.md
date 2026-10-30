# M11 GitHub Actions / Pages 운영 설정

## 현재 구현과 실행 전제

`.github/workflows/central-notice-pages.yml`은 매일 **07:17 KST (22:17 UTC)** 및 수동 실행을 지원한다.
workflow는 JSON 문법으로 쓴 YAML 1.2다. Python 표준 json으로 구조를 검사할 수 있으며
별도 YAML parser/pip package/Jekyll/npm 설치는 없다. runner는 ubuntu-latest, Python 3.13이다.
로컬 Windows `.venv`나 절대 Python 경로를 GitHub에 올리지 않는다.

현재는 저장소 주소/기본 브랜치/Pages 설정이 제공되지 않아 실제 GitHub 실행/URL 검증을 수행하지 않았다.
아래 설정을 완료해야 한다. M00~M10의 데이터/판정/CLI 계약은 그대로다.

## GitHub에서 설정할 순서

1. GitHub 저장소를 만들거나 선택하고 프로젝트 파일을 **기본 브랜치 루트**에 반영한다.
   `.github/workflows/central-notice-pages.yml` 경로를 유지한다. 이 작업에서 로컬 Git 명령/업로드는 수행하지 않았다.
   `.venv`, `.env`, credentials, 실제 key는 업로드하지 않는다. 키는 다음 Secret에만 입력한다.
2. Settings → Secrets and variables → Actions → **Secrets**에 `GEMINI_API_KEY`를 등록한다.
   배포 job의 environment secret이 아닌 **repository Actions secret**으로 설정한다(build job에서 사용).
3. 같은 화면 **Variables**에 `GEMINI_MODEL`을 명시적으로 등록한다.
   M08의 구조화 JSON API를 지원하며 해당 키에서 사용할 수 있는 모델 ID를 선택한다. 자동 기본값은 없다.
4. 기본 브랜치 `config/sites.yaml`의 `sites`에서 구현된 수집원 **하나 이상**의 `enabled`만 `true`로 바꾼다.
   최소 한 곳으로 시작할 수 있다. JSON 문법을 유지하고 47개 설정/원본 coverage는 삭제하지 않는다.
   구현된 ID: `khidi_business`, `kised_bid_public`, `rda_bid`, `seoul_rnd_notice`, `kipa_bid`.
   KISTA/RIPC 등 미구현 source는 계속 false다. 이 작업에서는 실제 config의 false를 변경하지 않았다.
5. Settings → Actions에서 이 저장소의 workflow와 사용하는 공식 Actions를 허용한다.
   state artifact 조회에는 Actions read, Pages 배포에는 Pages write/ID-token write 권한이 필요하며 workflow에 선언되어 있다.
   조직 정책이 이 권한/Actions 사용을 막으면 관리자 설정이 필요하다. 추가 PAT/개인 credential은 필요 없다.
6. Settings → Pages → Build and deployment → Source를 **GitHub Actions**로 선택한다.
   `github-pages` environment의 배포 브랜치/승인 정책도 기본 브랜치 실행을 허용해야 한다.
7. Actions → **Central notice daily and Pages** → Run workflow에서 기본 브랜치를 선택한다.
   **최초 실행에만** `bootstrap_state=true`로 설정한다. 다음 수동 실행은 false(기본값)다.
   다른 브랜치를 선택하면 build/deploy가 실행되지 않는다. 스케줄도 기본 브랜치 기준이다.
8. build/deploy 성공 후 deployment 환경에 표시되는 **실제 Pages URL**을 확인한다.
   그 URL 뒤의 `/notices.json`, `/metadata.json`을 각각 열어 generated_at/count가 같은 snapshot인지 확인한다.
   프로젝트 Pages는 보통 `https://<owner>.github.io/<repo>/...` 형태이지만 실제 표시 URL을 사용한다.
   JSON 전용 배포이므로 사이트 루트에 index.html/대시보드는 없다.

수동 workflow/키 사용/두 URL 확인까지 끝나야 M11을 PASS로 바꿀 수 있다.
현재 로컬 산출물만으로 실배포 성공을 판정하지 않는다.

## 실행/배포 경계

```text
checkout → Python 3.13 → offline unittest
→ 설정 preflight (키 값 미출력)
→ 이전 central-state-v1 artifact 검색/복원/검증
→ python -m src.main --data-dir .run/data --public-dir .run/public
→ 저장된 Notice snapshot과 feed/metadata 일치 검증
→ .run/pages에 JSON 두 개만 생성
→ central-state-v1 보관 → Pages artifact 업로드 → Pages 배포
```

- 키/모델은 preflight 및 pipeline step에만 env로 주입한다. unit test/Pages job/진단 artifact에는 키를 전달하지 않는다.
- 실제 source/AI/storage/feed 코드는 변경하지 않았다. runner의 `python`은 setup-python으로 지정한 3.13이다.
- concurrency group은 workflow 전체에서 하나이며 진행 중 실행을 취소하지 않는다. 동시 writer/배포 경합을 줄인다.
- M10 exit 0은 정상, 1은 부분 실패다. 1은 warning/summary를 남기고 유효한 snapshot/feed를 보관·배포한다.
  부분 실패만으로 Actions run을 red로 바꾸지는 않는다. summary의 exit code와 diagnostics를 확인한다.
- exit 2 이상/테스트·복원·검증 실패는 build 실패로 처리하여 새 Pages 배포를 막는다.
  기존 Pages 배포를 빈 내용으로 덮어쓰지 않는다.
- Pages artifact 경로는 `.run/pages`뿐이다. data/원본 본문/.env/credential/진단 파일은 Pages에 포함하지 않는다.
- state/진단 업로드는 숨김 경로의 **명시한 파일만** include-hidden-files=true로 허용한다.
  .run 전체나 프로젝트 루트를 artifact에 올리지 않는다.
- staging은 보관 snapshot으로 M09 build_feed를 다시 계산해 두 JSON과 정확히 비교한다.
  count/시각/schema 불일치, 오래된 public, 추가 내부 필드, 기존 dirty staging은 거부한다.
- pipeline/상태/Pages 전체 transaction은 아니다. Pages 배포가 실패해도 새 정상 state artifact가 남으면 다음 실행에서 복원한다.
  이 경우 다음 정상 실행으로 feed를 다시 생성한다. M10의 파일별 atomic write 계약은 유지된다.

## 실행 간 상태 / 복구

GitHub hosted runner의 디스크는 다음 실행에 유지되지 않는다. 따라서 `data` 없이 매번 처음 시작하면
모든 공고가 NEW가 되고 Gemini가 반복 호출된다. 이를 피하려고 **central-state-v1** artifact에
`notices.json`, `scraper_status.json`을 함께 보관하고 다음 실행 시작에 복원한다.

- 최신 artifact는 같은 저장소/기본 브랜치의 기록에서 선택한다. API 목록은 pagination한다.
- 검증된 정상/부분 성공 pipeline만 새 state artifact를 보관한다. 손상/미완성 state를 정상 백업으로 업로드하지 않는다.
- artifact 보존 요청은 90일이다. 저장소/조직 보존 정책도 이를 허용해야 한다(더 짧은 정책이면 workflow 보존값 조정).
- state artifact는 repository 읽기 권한자의 다운로드 대상이며, 공개 저장소에서는 공개 공고 본문/분석 이력도 공개될 수 있다.
  이 파일에는 실제 API key/회사 실적/credential을 넣지 않는다. Pages에는 이 artifact를 배포하지 않는다.
- 보존 정책/삭제/장기 비실행으로 artifact가 없어지거나 만료되면 **자동 빈 초기화하지 않고 중단**한다.
  운영자는 최신 정상 state artifact를 별도로 백업해 둘 수 있다.
- `STATE_MISSING`은 최초 수동 실행의 bootstrap_state=true로만 빈 시작을 허용한다.
  기존 기록이 있으면 bootstrap=true라도 그 기록을 복원한다. `STATE_EXPIRED`는 bootstrap으로 우회하지 않는다.
- 만료/유실된 기존 운영 상태는 백업 복원이 우선이다. 백업을 동일 이름 state artifact로 복구하는 관리 작업은 별도다.
  **이력을 버리고 의도적으로 새로 시작하는 경우에만** 기존 만료 state artifact를 정리한 뒤 수동 bootstrap을 사용한다.
  이 경우 first_seen/cache 이력이 사라지고 API 분석 비용이 다시 발생한다.
- M08 정책대로 FAILED/PENDING 자동 재시도는 없다. 다음 실행의 EXISTING은 API를 호출하지 않는다.

## 오류 확인

1. Actions run의 첫 실패 step을 확인한다. unittest, config, restore, pipeline, staging, upload, deploy가 각각 분리되어 있다.
2. pipeline step은 종료 코드(0/1/2)를 Summary에 남기고 안전한 단계/분석 코드 로그를 출력한다.
3. 항상 실행하는 diagnostics step은 저장 건수, source별 상태/count, 분석 status별 count만 출력한다.
   raw body/title/AI reason/원문 오류/환경변수는 출력하지 않는다.
4. `central-diagnostics-<run_id>-<attempt>` artifact(14일)에서 동일한 안전한 JSON을 내려받을 수 있다.
   checkout/Python setup 자체가 실패하면 helper/진단 artifact도 없을 수 있으므로 해당 step 로그를 먼저 본다.
5. `NO_ENABLED_SITES`/`INVALID_GEMINI_*`는 위 설정 2~4, `STATE_*`는 상태 복구,
   Pages 403/404/승인 대기는 위 설정 5~6을 확인한다. 키 값을 로그로 출력하며 확인하지 않는다.

## 오프라인 검증 / 공식 근거

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m tools.actions_support --help
.\.venv\Scripts\python.exe -m json.tool .github/workflows/central-notice-pages.yml > $null
```

전체 unittest 및 JSON-syntax YAML 구조/권한/실행 순서/허용 배포 경로를 검사한다.
이는 GitHub expression/server-side workflow validator나 실제 Actions 실행을 대신하지 않는다.
로컬에는 PyYAML/actionlint를 추가 설치하지 않았다.

구현 시 확인한 공식 문서:

- [GitHub Pages custom workflow](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages): Pages artifact/배포 job/권한.
- [Workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax): schedule/dispatch/concurrency.
- [Actions artifacts API](https://docs.github.com/en/rest/actions/artifacts): repository artifacts 검색/Actions read.
- [download-artifact](https://github.com/actions/download-artifact): artifact ID 및 run-id/token을 통한 이전 실행 복원.
