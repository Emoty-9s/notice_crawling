# M13 Result

## Status

**PASS** — MILESTONES_V2.md M13 Local Performance Database.
검증일: 2026-11-02 (Asia/Seoul). 로컬 SQLite CRUD/CSV import/검색 및 전체 회귀 검증 완료.
M11 실제 배포/M12 실제 원격 다운로드 제한은 그대로이며 M13에는 네트워크가 필요 없다.
M14 매칭 및 UI는 구현하지 않았다.

## Implementation / Files

생성: src/local_client/performance.py, tests/test_performance.py, docs/progress/M13_RESULT.md.
수정: .gitignore, README.md, docs/progress/CURRENT_STATE.md.

기존 M00~M12 코드, src.local_client의 feed API/CLI/cache, 중앙 pipeline/AI/feed/Actions 및 운영 config/public/data는 변경하지 않았다.
새 모듈은 stdlib sqlite3/csv/json/dataclasses만으로 로컬에서 동작하며 중앙·GitHub·Gemini·feed 모듈을 import하지 않는다.
HTTP 호출, 업로드, 실적의 public projection/AI 입력 연결은 없다. 기존 workflow artifact 경로도 그대로다.
실제 회사 실적/운영 DB는 생성하거나 읽지 않았으며 테스트는 모두 임시 폴더의 합성 데이터다.

## Local Data / API

기본 위치는 cwd와 무관한 프로젝트 local/performance.db다. PerformanceStore(path)로 사용자 데이터 경로를 지정할 수 있다.
import만으로 DB를 만들지 않는다. PerformanceStore 생성 시 부모 디렉터리/초기 schema를 만들거나 기존 DB를 검증한다.
각 작업은 짧은 SQLite connection/transaction으로 처리하고 명시적으로 닫는다. 별도 close 호출은 필요 없다.

```python
from dataclasses import replace
from src.local_client.performance import Performance, PerformanceStore

store = PerformanceStore()  # 또는 PerformanceStore(user_database_path)
record = Performance(
    performance_id='P001', project_name='예시 IP 전략 과제', client='예시 고객',
    year=2025, technical_field='반도체', work_type='특허분석',
    keywords=['반도체', 'IP-R&D'], description='예시 설명', attorneys=['담당 A'], notes='',
)
store.create(record)
saved = store.get('P001')
store.update(replace(saved, notes='수정 메모'))
results = store.search('반도체', year=2025, limit=100, offset=0)
deleted = store.delete('P001')
count = store.import_csv(csv_path)  # 기본 UTF-8/BOM 허용
```

Performance는 frozen dataclass이며 모든 최소 필드를 가진다.

| 필드 | 타입/규칙 |
| --- | --- |
| performance_id, project_name | 필수 비어 있지 않은 str, 앞뒤 공백 제거 |
| client, technical_field, work_type | str, 기본 빈 문자열, 앞뒤 공백 제거 |
| year | int 1~9999 또는 None, bool/float/string 제외 |
| keywords, attorneys | str list/tuple 입력, immutable tuple로 보관, SQLite에서는 JSON 배열 TEXT |
| description, notes | str, 기본 빈 문자열, 개행/공백 보존 |

모든 텍스트는 유효한 UTF-8이며 NUL을 거부한다. 목록 항목은 공백 제거 후 비어 있으면 오류다.
ID는 사용자가 공급한다. create의 중복은 DuplicatePerformanceError이며 자동 병합/덮어쓰지 않는다.
get은 없으면 None, delete는 없으면 False다. update는 같은 ID의 전체 record 교체이며 없으면 PerformanceNotFoundError다.
부분 수정은 dataclasses.replace를 사용한다. 잘못된 입력은 PerformanceValidationError다.

검색은 10개 필드에서 Unicode casefold 기반의 문자 그대로 부분 문자열 검색이다.
SQL 값은 parameter binding하며 `%`, `_`, 따옴표를 wildcard/SQL로 실행하지 않는다.
빈 query는 전체 목록이며 기본 최대 100개다. year 필터, limit/offset을 지원한다.
정렬은 year 내림차순(None 마지막), 같은 연도는 performance_id 오름차순이다. 가중치/점수/공고 매칭은 없다.

## CSV Contract / Failure Handling

필수 header는 아래 10개이며 순서는 자유롭다. 누락/중복/추가 header는 오류다.

```csv
performance_id,project_name,client,year,technical_field,work_type,keywords,description,attorneys,notes
P001,예시 과제,예시 고객,2025,반도체,특허분석,반도체;IP-R&D,예시 설명,담당 A;담당 B,
```

- 기본 utf-8-sig로 UTF-8 BOM을 허용한다. 필요한 경우 encoding='cp949' 등 명시적 인자를 줄 수 있다.
- keywords/attorneys는 세미콜론 구분이다. 앞뒤 공백/빈 항목을 제거하며 빈 셀은 빈 tuple이다. 항목 안의 세미콜론 escape는 지원하지 않는다.
- year 빈 셀은 None, 값이 있으면 ASCII 숫자 연도만 허용한다. 나머지 선택 텍스트 빈 셀은 빈 문자열이다.
- 표준 CSV quoting으로 쉼표/여러 줄 설명을 지원한다. header만 있으면 0건, 완전한 빈 파일은 header 오류다.
- 모든 행의 parsing/모델 검증을 먼저 수행한 뒤 **하나의 transaction으로 전체 insert**한다.
- 잘못된 행/encoding/quoting/열 수/CSV 내부 중복 ID는 저장 전에 거부한다.
- 기존 DB ID와 중복되거나 SQL/commit 오류가 발생하면 이번 import 전체를 rollback한다. skip/upsert 모드는 없다.
- CSVImportError는 고정 code와 가능한 CSV 물리 줄 번호만 제공하며 실적 내용/원문 오류를 포함하지 않는다.
- 재수입 중복도 오류이며 기존 실적을 변경하지 않는다. 입력 CSV 자체는 수정하지 않는다.

기존 DB는 application_id=PERF, user_version=1, 컬럼 schema를 검증한다. 열 때 quick_check도 수행한다.
손상/타 용도 DB/미지원 버전/예상 밖 schema는 PerformanceDatabaseError이며 자동 삭제/초기화/migration하지 않는다.
작업 중 DB가 사라지면 빈 DB를 재생성하지 않는다. DB 잠금/I/O/SQL 오류는 안전한 고정 진단으로 반환한다.
SQLite transaction rollback으로 기존 데이터를 보존한다. 임의 손상 파일의 복구까지 제공하지는 않는다.

## Privacy / Git Boundary

.gitignore는 local/ 전체와 일반적인 DB/SQLite 파일 및 journal/WAL/SHM을 제외한다.
입력 CSV는 local/imports/ 등 local/ 아래에 두는 것을 권장한다. 별도 사용자 경로/백업 파일은 사용자가 관리한다.
이 모듈에는 네트워크/AI 코드가 없으며 기존 중앙 실행/배포가 로컬 실적 저장소를 읽도록 연결하지 않았다.
실적 내용을 로그로 출력하거나 Secret/credential을 추가하지 않았다.

## Tests / Actual Results

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_performance.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

M13 신규 **28 tests OK**. 전체 **301 tests OK**(기존 273 + 신규 28), 실패/오류 0, exit code 0.
모든 DB/CSV는 임시 폴더의 합성 데이터이며 실제 HTTP 진입점은 금지 mock으로 막았다.

검증: 초기 schema 생성, 10필드 왕복 CRUD/누락 ID, 중복 거부, 재생성한 store의 지속성,
모델 타입/연도/텍스트 검증, BOM/열 순서/쉼표/개행/목록/빈 연도 CSV, 잘못된 header/행/encoding/quoting,
CSV 내/DB와의 중복 및 재수입, SQL trigger로 중간 insert 실패를 발생시킨 전체 rollback,
update/delete SQL 오류와 DB 잠금 시 데이터 보존, 손상/타 용도/미지원 schema/삭제 DB의 자동 초기화 금지,
검색 전 필드/한글/Unicode casefold/연도/정렬/페이지/SQL injection·wildcard 문자 처리,
feed/Gemini 호출 금지 상태에서 CRUD/import/search 성공.

## Blocker / Limits / Next

- M13 구현 blocker 없음. Python 기본 sqlite3 외 추가 설치/외부 API/Secret이 필요 없다.
- 자동 schema migration, DB 백업/복구, CSV streaming 대량 import는 없다. CSV는 전체 검증을 위해 메모리에 적재한다.
- 동시 쓰기는 SQLite 잠금과 timeout(기본 5초)을 따른다. 잠금 오류 시 호출자가 다시 시도해야 한다.
- 실적 등록/검색은 Python API로 제공하며 UI/별도 CRUD CLI/공고 매칭은 추가하지 않았다.

다음: 사용자 실적 CSV를 로컬에서 import해 필드/검색을 확인할 수 있다.
M11/M12의 실제 배포·다운로드 확인은 별도로 남아 있다. M14 이후는 사용자 요청 전 진행하지 않는다.
