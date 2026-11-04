# 사업공고 모니터링 시스템

공고 사이트의 신규/수정 공고를 수집하고, Gemini가 특허법인/특허사무소의
수행 주체 참여 가능성을 판정하여 공통 JSON으로 제공합니다.
현재 개발 범위는 `MILESTONES_V2.md`를 따릅니다. 회사 실적 매칭은 로컬 영역에서 수행합니다.

중앙 구현은 **M10 — Central End-to-End Pipeline**, 로컬 구현은 **M12 feed 동기화 / M13 실적 DB / M14 규칙 매칭 / M15 UI 및 로컬 실적 업로드**입니다.
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
중앙 storage/history는 실패/빈 목록/비활성/미관측/마감 공고를 포함한 관측 이력을 보존합니다.
마감 후 기간 경과를 이유로 history를 삭제하지 않습니다. 공개 feed v2에는 현재 분석 정책
`patent-firm-participation-v2`와 본문 hash가 일치하는 SUCCESS 중 특허법인이 참여 가능하고
현재 유효한 공고만 포함합니다. 확정 마감일은 한국 날짜 기준 당일까지 유효하며,
마감일 미상/상시 공고는 명백한 종료 근거가 없으면 유지합니다.
이전 policy의 성공 결과는 재분석하고 마감 공고는 Gemini 호출 전에 제외합니다.
실행당 기본 60회, 실제 provider 요청은 최소 6초 간격이며 429 이후 해당 run의 호출을 중단합니다.
NEW는 현재 중앙 run에서 발견한 신규 공고의 `is_new`이며 로컬 확인 이력과 독립적입니다.
로컬은 동기화/오프라인 로딩/1분 주기 갱신에서 유효 공고를 표시하며 producer cache를 보존합니다.
7개 operational source의 수집 범위는 최신 최대 3페이지이며 checked-in 설정은 비활성으로 유지합니다.
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

Python API의 기존 `import_csv`는 performance_id/project_name/client/year/technical_field/work_type/keywords/description/attorneys/notes의 10개 header를 사용합니다.
Windows의 `실적 업로드`는 아래 설명처럼 header alias와 자동 탐색을 사용하므로 이 고정 양식을 요구하지 않습니다.
keywords/attorneys는 세미콜론 구분이며 UTF-8 BOM을 허용합니다. 한 행이라도 오류/중복이면 이번 import 전체를 취소합니다.
중복 ID는 자동 덮어쓰지 않습니다. local/ 전체와 DB 파일은 Git 제외이며 실적은 중앙/GitHub/Gemini로 전송하지 않습니다.
정확한 필드/CSV/API/오류 계약은 [M13 결과](docs/progress/M13_RESULT.md)를 참고합니다.

## Windows 실적 업로드

공고 목록 위 `실적 업로드` → 파일 선택 → 미리보기 → 체크 확인 → `저장` 순서로 사용합니다.
맨 왼쪽 `선택` 칸은 기본 전체 체크이며 칸 클릭/Space로 해제할 수 있습니다.
`전체 선택`/`전체 해제`/`선택 반전`과 선택 건수를 제공합니다. 체크한 행만 insert/update에 전달하고,
체크 해제한 행은 사용자 제외 건수로 알립니다. 0건 선택이면 저장하지 않습니다.
선택 상태는 미리보기 UI에만 있으며 DB의 업무 필드로 저장하지 않습니다.
`.xlsx`(openpyxl), `.xls`(xlrd), `.csv`(UTF-8/UTF-16 BOM/CP949)를 지원합니다.
고정 template 없이 여러 sheet와 처음 60행의 header 후보를 찾고, alias와 보수적인 cell 패턴으로 매핑합니다.
추정한 매핑·미분류 열·불완전한 값은 `확인 필요`로 표시하며 저장할 수 있습니다.
빈 sheet/빈 행/반복 header/합계·총계·소계·TOTAL은 실적에서 제외합니다.

관리번호는 문자열로 유지합니다. Excel 문자열의 선행 0과 `000000` 같은 정수 표시 형식을 지원합니다.
Excel이 이미 숫자로 저장하면서 잃어버린 선행 0은 추측해서 복원하지 않습니다.
원본 행/수식/숫자 형식, 정규화 필드, searchable_text, 매핑 근거는 기존 DB 안의
추가 테이블 `performance_uploads_v1`에 로컬 저장합니다. 원본 파일은 복사하거나 수정하지 않습니다.
암호화된 workbook은 지원하지 않으며, 수식을 실행하지 않습니다. XLSX에 계산 cache가 없는 수식은 확인 필요로 남깁니다.

중복은 정규화한 실적명·고객·연도, 관리번호와 실적명·고객 맥락, 안정적인 행 fingerprint로 판정합니다.
관리번호만으로 합치지 않으며, 중복은 기존 기록을 유지하고 건수를 알립니다. 정상 행은 일부 행 오류와 독립적으로 저장합니다.
실적 기본 테이블 v1과 matcher 계산은 유지합니다. 업로드 데이터를 기존 Performance 모델로 연결하고,
관리번호·금액은 matcher 설명 텍스트에서 제외하며 미분류 업무 텍스트는 포함합니다.
저장 후 실적을 다시 읽어 현재 공고의 매칭을 갱신합니다. 기존처럼 매칭 기준 연도는 직접 입력합니다.

회사 데이터는 GitHub/Pages/Actions/Gemini/외부 API/분석 서비스로 보내지 않습니다.
개발 실행의 Excel reader 설치는 `python -m pip install -r requirements-desktop.txt`,
desktop 테스트 설치는 `python -m pip install -r requirements-test-desktop.txt`입니다.
중앙 수집용 requirements와 Actions 설정은 변경하지 않습니다.
파일당 50MB, 압축 해제 150MB, sheet당 50,000행/256열, workbook 전체 500,000셀 제한이 있습니다.
미리보기는 이전/다음으로 1,000행씩 표시합니다. 체크 상태는 페이지를 넘겨도 유지되며,
전체 선택/해제/반전은 모든 페이지에 적용합니다.

### 저장된 실적 관리

`실적 관리`에서 실제 로컬 DB 전체를 최신 연도 순으로 조회하고 관리번호·실적명·고객·분야·업무유형을 검색합니다.
목록 헤더 클릭 정렬, 단건 수정, Ctrl/Shift 복수 선택 후 확인 대화상자를 거친 삭제를 지원합니다.
수정창은 연도·관리번호·실적명·고객·기술분야·업무유형을 편집합니다. 기술분야는 21개 중 최대 3개,
업무유형은 기존 matcher category group의 허용값만 선택합니다.
변경한 값은 `user` provenance로 보존하고, 관리번호는 문자열을 유지하며 PK는 바꾸지 않습니다.
원본 Excel 행은 유지합니다. 수정/삭제와 enrichment/upload metadata는 같은 transaction으로 처리합니다.
다른 창에서 바뀐 실적은 오래된 revision으로 덮어쓰거나 삭제하지 않습니다.
업로드·수정·삭제 후 열린 관리 목록과 공고 매칭을 다시 읽으므로 재실행이 필요 없습니다.
조회만으로 없는 DB를 생성하지 않으며, 빈 DB에는 업로드 안내만 표시합니다.

### 오프라인 로컬 AI 보조 분류

동봉한 `intfloat/multilingual-e5-small` 공식 INT8 ONNX 모델을 CPU 전용 ONNX Runtime으로 실행합니다.
한국어·영어를 지원하며 모델은 MIT, tokenizer runtime은 Apache-2.0입니다.
선택 근거와 라이선스/평가/실측은 [로컬 AI 결과](docs/progress/LOCAL_AI_ENRICHMENT_RESULT.md)를 참고하세요.
실행 중 다운로드, Hugging Face API, Gemini, OpenAI, 외부 inference는 사용하지 않습니다.
PyTorch·Transformers·Hugging Face Hub 클라이언트는 EXE에서 제외합니다.

원본/alias/parser 결과를 우선하고, 비어 있는 기술분야·업무유형·핵심어를 모델로 보조합니다.
제목 추론은 원본 셀 후보 중 하나를 선택하는 추출형이며 새 제목을 생성하지 않습니다.
관리번호·고객·날짜·연도·금액은 모델 쓰기 대상이 아닙니다. raw_source는 변경하지 않습니다.
기술분야는 기존 20개 후보에 소부장을 추가한 21개 후보만 사용하고, 업무유형은 기존 matcher의 4개 category group
대표값(특허분석/기술사업화/특허출원/분쟁대응)을 재사용합니다.
`technical_field`는 primary 후보, `technical_fields`에는 허용 후보를 최대 3개 저장합니다.
제목의 구체 기술어는 evidence/keywords에만 보존하며 기술분야 라벨로 생성하지 않습니다.
미리보기에도 taxonomy 후보명만 표시합니다. 사용자 선택과 DB 저장 경계에서도 후보 목록을 검증합니다.
제목 전체와 제목/설명의 독립 phrase를 각각 embedding하고, 대표 example들과 비교합니다.
제목의 근거가 설명의 일반 문구보다 우선합니다. taxonomy에 없는 원문 phrase는 분야가 아니라 근거로 보존합니다.
키워드는 원문에서 추출하여 의미 유사도로 정렬하며, 기본 최대 8개입니다.

기술분야는 margin을 탈락 조건으로 쓰지 않습니다. 제목 전체 cosine ≥0.84, 독립 phrase ≥0.89,
비기술 참조보다 ≥0.025 높은 근거를 사용합니다. 서로 다른 phrase는 각각 분야를 추가할 수 있습니다.
한 제목 전체에서 추가 분야를 고를 때는 ≥0.91(세 번째 ≥0.93)을 요구합니다.
기존 업무유형 판정은 cosine ≥0.79, margin ≥0.010, 비기술 참조 차이 ≥0.012 정책을 유지합니다.
점수는 확률이 아닙니다. 근거가 부족하거나 비기술 텍스트면 미분류로 남기며, 원본·사용자값은 보호합니다.
기술분야·업무유형을 미리보기에서 수정하면 출처 `user`로 저장합니다.
`미분류 실적 분석`은 기존 DB의 빈 필드를 처리하며, `기존 AI 결과도 갱신`을 체크해야
이전 AI 값도 재분석합니다. 사용자값·명시적 값·나중의 DAO 수정값은 보호합니다.
동시 편집으로 DB가 바뀌면 오래된 분석 저장을 거절하고 원본을 유지합니다.

파일 파싱과 추론은 별도 로컬 프로세스에서 batch 처리하며 진행 건수와 취소 버튼을 제공합니다.
UI와 모델 import의 GIL을 분리하고, 작업 후 프로세스를 종료해 모델 메모리를 반환합니다.
실행 시작이나 일상 대시보드 사용 시에는 모델을 열지 않습니다.
모델 오류 시 기본 파싱 결과로 미리보기를 계속 표시하고 저장할 수 있습니다.
출처/유사도/모델·정규화 버전/검토 상태는 기존 DB의 추가 테이블 `performance_enrichment_v1`에 저장합니다.
기존 `performances` 스키마와 matcher 점수는 유지합니다. 승인된 broad 분야와 세부 태그를
최소 keyword adapter로 연결하고, 근거/원문 phrase/상위 5개 후보는 로컬 metadata에 보존합니다.

실제 로컬 DB 개발 진단(기본은 읽기 전용, stdout/summary 파일은 통계만):
```powershell
.\.venv\Scripts\python.exe tools/diagnose_performance_fields.py --db "실제 DB 경로" --view
```
제목·top5·기존 탈락 이유·직접 기술어는 로컬 진단 창에서만 확인합니다.
`--apply`를 명시하면 로컬 SQLite 백업 후 미분류 실적만 저장합니다.
실제 DB가 없으면 `REAL_DATABASE_NOT_FOUND`를 반환하며 검증용 DB로 대체하지 않습니다.

개발/빌드 시 모델 확보(사용자 실행에서는 수행하지 않음):
```powershell
.\.venv\Scripts\python.exe tools/fetch_performance_model.py download
.\.venv\Scripts\python.exe tools/prepare_model_distribution.py
```
모델과 tokenizer SHA-256을 검증하며, 모델이 없으면 빌드가 실패합니다.
완전 오프라인 대시보드 사용은 기존 `--offline` 옵션으로 GitHub 시작 동기화도 끌 수 있습니다.

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

UI는 기존 matcher를 그대로 호출하고 매칭 시 DB를 SQLite mode=ro로 읽습니다.
`실적 업로드`에서 선택한 파일은 미리보기 후 저장을 눌렀을 때만 로컬 DB에 반영합니다.
DB가 없어도 공고는 볼 수 있습니다. 매칭에 사용할 DB는 기존 M13 절차로 준비합니다.
동기화 실패 시 같은 feed 주소의 마지막 정상 cache를 사용하고 노란색 상태를 표시합니다. cache도 없으면 빨간색 오류입니다.
`--offline`은 기존 cache만 표시하고 네트워크를 사용하지 않습니다. `--base-url`로 공개 feed 디렉터리를 지정할 수 있습니다.
NEW는 로컬 사용자가 아직 확인하지 않은 공고입니다. 생성일이나 앱 실행 간격과 무관하며,
상세 열기 또는 공고별 `확인 처리`를 눌렀을 때만 일반 공고(SAVED)로 바뀝니다.
확인 후 수정된 공고는 UPDATED로 구분하고 다시 확인하면 일반 공고로 전환합니다.
확인 이력은 cache 옆 `<cache 파일명>.<사용자 식별 해시>.seen.json`에 feed 출처별로 저장하며 중앙에 전송하지 않습니다.
사용자 이름 대신 로컬 프로필 경로의 해시를 사용해, 사용자 지정 cache 경로를 공유해도 확인 이력은 분리합니다.
EXE 기본 경로는 Windows 사용자별 `%LOCALAPPDATA%/NoticeCrawling/cache`입니다.
cache만 갱신해도 확인 이력은 유지됩니다. 기존 cache는 확인 이력이 아니므로 최초 적용 시
보존 중인 모든 미확인 공고가 NEW로 표시됩니다. 중앙 Notice/Gemini 상태는 변경하지 않습니다.
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
기존 정상 파일은 설정에서 지정할 수 있고 --cache/--db 옵션도 유지합니다. 공개 공고 cache만 동기화하며,
실적 DB는 사용자가 업로드 미리보기의 저장을 누를 때만 생성/추가합니다. 실적은 외부로 전송하지 않습니다.
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
