# M12 Result

## Status

**PASS (오프라인 구현/검증)** — MILESTONES_V2.md M12 Local Client / Feed Sync.
검증일: 2026-11-02 (Asia/Seoul). M11 실제 배포/공개 URL 검증은 계속 PARTIAL이다.
M12의 실제 GitHub HTTP smoke는 공개 URL 미확정으로 수행하지 않았다.

## Implementation / Files

생성: src/local_client/__init__.py, sync.py, __main__.py, tests/test_local_client.py, docs/progress/M12_RESULT.md.
수정: .gitignore(local/cache 제외), README.md(로컬 실행 안내), docs/progress/CURRENT_STATE.md.

중앙 src/main.py/src/pipeline.py, M00~M11 코드/워크플로/공개 schema 및 기존 public/config/data는 변경하지 않았다.
로컬 클라이언트는 중앙 pipeline, storage, AI, scraper를 import하거나 실행하지 않는다.
표준 라이브러리 urllib/json/tempfile/os/unittest만 사용하며 외부 의존성/credential이 필요 없다.
M13 이후 DB/실적 매칭/UI/자동 스케줄은 구현하지 않았다.

## Execution / Handoff

프로젝트 루트 PowerShell에서 실제로 확인한 Pages 배포 디렉터리 URL을 사용한다.

```powershell
.\.venv\Scripts\python.exe -m src.local_client --help
.\.venv\Scripts\python.exe -m src.local_client --base-url 'https://<owner>.github.io/<repo>/'
.\.venv\Scripts\python.exe -m src.local_client --base-url 'https://<owner>.github.io/<repo>/' --cache-dir '.\local\cache' --timeout 30
```

URL은 notices.json 파일 자체가 아닌 두 JSON이 위치한 디렉터리다. 위 URL은 형식 예시이며 확정된 운영 URL이 아니다.
HTTP/HTTPS를 지원하며 userinfo/query/fragment/control character 및 잘못된 port는 요청 전에 거부한다.
기본 cache는 실행 cwd와 무관한 프로젝트 local/cache/snapshot.json이다. --cache-dir로 사용자 데이터 경로를 지정할 수 있다.
local/cache는 .gitignore 대상이며 테스트는 임시 폴더만 사용한다. 별도 사용자 cache 경로는 사용자가 관리한다.

프로그램 API:

```python
from src.local_client.sync import FeedClient, SyncError

client = FeedClient(base_url, cache_dir=cache_directory, timeout=30)
result = client.sync()
notices = result.feed['notices']
metadata = result.metadata
```

FeedClient 생성/import는 네트워크/저장을 수행하지 않는다. sync가 metadata.json → notices.json 순으로 다운로드한다.
transport(url, timeout) → bytes를 주입할 수 있다. load_cache()는 네트워크 없이 검증된 snapshot dict를 반환한다.

| 결과 | 의미 | CLI 종료 코드 |
| --- | --- | --- |
| UPDATED | 검증된 새 pair를 로컬에 저장 | 0 |
| UNCHANGED | 기존 pair와 같아서 재저장 없음 | 0 |
| FALLBACK | 네트워크/검증/저장 실패, 같은 URL의 마지막 정상 cache 반환 | 1 |
| SyncError | 설정 오류 또는 실패 후 사용할 정상 cache 없음 | 2 |

result.error_code는 FALLBACK 원인을 나타내는 고정 코드다. 원문 HTTP 오류/응답 본문/credential은 로그에 넣지 않는다.
CLI는 상태/공고 수/생성 시각만 출력한다. feed 데이터는 API 반환값이나 cache에서 읽는다.

## Validation / Cache Contract

- 두 문서 schema_version이 정확한 int 1인지 검사한다(bool/float/string 제외).
- UTF-8/JSON, 중복 key, NaN/Infinity, lone surrogate를 검사한다. 문서별 응답 크기는 최대 16 MiB, timeout 기본 30초다.
- metadata 필드/count/시각, feed 필드/notices 배열, 두 문서 생성 시각·개수 일치 및 notice_id 중복을 확인한다.
- M09의 공개 필드 15개와 타입을 검증한다. nullable 날짜/빈 summary/빈 keywords를 지원하며 내부 content_text 등은 받지 않는다.
- 매번 두 JSON을 검증한다. 동일 내용 재수신은 UNCHANGED이며 API 호출/수집/중복 공고 추가/파일 재저장은 없다.
- cache envelope는 base_url/feed/metadata다. 같은 정규화 URL의 정상 cache만 fallback에 사용한다.
- cache도 매번 검증한다. 손상 cache를 빈 정상 데이터로 간주하지 않으며, 정상 원격 다운로드가 성공하면 교체할 수 있다.

중앙 public 두 파일의 계약은 그대로 유지한다. 로컬 저장은 **단일 snapshot.json에 두 문서를 함께 저장**한다.
이는 M12의 로컬 경로 선택 범위에 해당하며, 두 파일을 순차 교체할 때 metadata만 새 값이 되는 문제를 피한다.
전체 직렬화 → 같은 디렉터리 임시 파일 → write/flush/fsync/close → os.replace 한 번이 commit 지점이다.
저장 실패 전까지 이전 snapshot은 유지하며 임시 파일 정리를 시도한다. 정상 cache가 있으면 저장 실패에도 이전 pair를 반환한다.

## Tests / Actual Results

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_local_client.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m src.local_client --help
```

M12 신규 **24 tests OK**. 전체 **273 tests OK**(기존 249 + 신규 24), 실패/오류 0, exit code 0.
CLI --help도 exit code 0. 실제 HTTP 진입점은 금지 mock으로 막고 fixture/임시 cache만 사용했다.

검증: 정상 mock 다운로드/producer build_feed 호환/체크인된 초기 public pair, 빈 feed, 동일 feed 무저장,
갱신 후 새 client 복원, timeout/URLError/HTTP 503/연결 오류/IncompleteRead fallback,
잘못된 UTF-8/JSON/중복 key/비표준 숫자/surrogate, 두 문서의 unsupported schema,
metadata count/시각 불일치, 누락/내부 필드/중복 ID/잘못된 타입, 손상 cache 복구 및 다른 URL cache 거부,
부분 다운로드, 부분 write/flush/fsync/replace/임시 파일 생성 실패의 이전 pair 보존/임시 파일 정리,
동일 디렉터리 단일 commit, 최초 저장 실패, timeout/URL preflight, 응답 크기, 실제 urllib request 인자, CLI 종료 코드.

## Blocker / Limits / Next

- M12 오프라인 구현 blocker 없음. M11의 실제 Pages 공개 URL이 확인되지 않아 실원격 다운로드는 미검증이다.
- 단일 writer 전제이며 동시 writer 병합/전원 장애 보장/과거 snapshot 이력 보관은 없다.
- 자동 재시도/백오프/ETag/rollback 방지 정책은 없다. 배포 도중 pair가 다르면 cache를 사용하고 다음 실행에서 다시 시도한다.
- 최초 실행부터 네트워크가 실패하거나 cache까지 손상됐다면 반환할 정상 데이터가 없으므로 명시적 오류다.
- 응답 제한 16 MiB를 초과하는 운영 feed는 별도 크기 정책 검토가 필요하다.

다음은 M11 배포 URL 확인 후 M12 실제 다운로드와 오프라인 재실행을 확인하는 것이다.
M13 이후는 사용자 요청 전 착수하지 않는다.
