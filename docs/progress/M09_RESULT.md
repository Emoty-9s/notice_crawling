# M09 Result

## Status

**PASS** — MILESTONES_V2.md의 M09 Public Notice Feed JSON.

검증일: 2026-10-30 (Asia/Seoul). 구현·전체 unittest·실제 파일 생성/JSON 읽기·후속 인계를 완료했다.

## Implementation / Files

생성:

- src/renderer/feed.py
- tests/test_feed.py
- public/notices.json
- public/metadata.json
- docs/progress/M09_RESULT.md

수정:

- src/renderer/__init__.py: 현재 모듈 역할 설명.
- docs/progress/CURRENT_STATE.md: M09 완료 및 V2 M10 인계.

표준 라이브러리만 사용하며 기존 Notice/GeminiResult, M03 clean_content_text,
M06의 내부 `_atomic_json` primitive를 재사용했다. 기존 core/AI/scraper 코드는 수정하지 않았다.

## Public Schema v1

notices.json 루트: schema_version=1, generated_at, notices(array).

| 공고 필드 | 내용 |
| --- | --- |
| notice_id, source_id, institution, title | 원본 Notice 식별/기관/제목 |
| category | Gemini의 공고 분류 |
| participation_type | Gemini의 참여 유형 |
| published_at, apply_start, apply_end | 원본 Notice 날짜, 미상은 null |
| url | 원문 상세 URL |
| summary | 본문 공백/NFC 정리 후 최대 300자 발췌 |
| keywords | Gemini keywords의 JSON array |
| relevance_reason | Gemini reason |
| first_seen_at, updated_at | 원본 관측/변경 시각 |

각 record는 위 15개 필드를 모두 포함한다. 별도 저장 파일이나 내부 모델을 몰라도 읽을 수 있다.
content_text 필드/전체 장문 본문, content_hash, analyzed_content_hash, Gemini 원본 객체,
score, last_seen_at은 배포하지 않는다. 요약은 AI 호출 없이 발췌하며 긴 경우 말줄임표를 포함해
300자 이하, 짧으면 정리한 본문 그대로, 본문이 없으면 빈 문자열이다.

metadata.json: schema_version=1, 동일 generated_at, notice_count(필터/중복 제거 후 개수).

## Filtering / Determinism

- 기본 포함 조건은 gemini.status=SUCCESS 및 gemini.relevant=true다.
- M08 인계에 따라 현재 content_hash와 analyzed_content_hash가 같고 category/participation_type/reason/keywords가
  존재하는 성공 결과만 포함한다. 실패/대기/미분석/irrelevant/미상 판단/오래된·불완전한 성공 결과는 제외한다.
- Notice status가 EXISTING이어도 유효한 관련 분석 결과면 포함한다. Gemini를 다시 호출하지 않는다.
- 정렬은 (source_id, notice_id) 오름차순이다. 동일 ID/공개 record 중복은 축약하고 충돌은 FeedInputError다.
- JSON은 UTF-8, 정렬된 객체 키, 2칸 indent, LF, 마지막 newline이다.
- generated_at은 필수 주입값이며 timezone 포함 ISO 문자열을 UTC Z로 정규화한다. 내부 시계 조회는 없다.
- 동일 입력/시각이면 같은 JSON bytes다. generated_at만 달라져도 공고 data 자체는 동일하다.
- 입력 객체/키워드를 수정하지 않고 공개 필드 allowlist를 통해 새 객체만 만든다.

## Tests / Verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

실제 결과: **210 tests OK**, 실패/오류 0, exit code 0.
M09 신규 18개 + 기존 192개 회귀 통과. 외부 API/네트워크는 사용하지 않았다.

검증 항목:

- relevant만 포함, irrelevant/FAILED/PENDING/NOT_ANALYZED/미상 결과 제외.
- 오래된 분석 hash/누락된 새 출력 필드 제외, NEW/UPDATED/EXISTING 관련 결과 포함.
- 빈 입력/모두 제외된 결과의 정상 schema, required 15필드/schema_version 및 null 날짜.
- participation_type/keywords/relevance_reason/분류/관측 시각 반영.
- 본문 요약 정리/최대 길이/빈 본문, 원본 content_text와 내부 필드·장문 끝부분 미배포.
- 입력 순서 변경/시각 변경에도 동일 공고 data, 동일 시각에서 JSON byte 동일성.
- UTC 정규화/잘못된 생성 시각 거부, 중복 축약/충돌 명시, 입력 비변경.
- 임시 디렉터리의 두 파일 독립 읽기, metadata count 일치, UTF-8/키 정렬/LF formatting.
- 입력 오류/첫 atomic replace 실패 시 기존 두 파일 유지 및 임시 파일 정리.

실제 public 파일도 write_feed로 생성 후 독립 json.loads로 읽어 확인했다.
generated_at: **2026-10-30T07:20:38.339587Z**, notice_count: **0**.
운영 data/notices.json은 아직 없으며, 분석하지 않은 fixture 공고나 가짜 Gemini 결과를 공개 데이터로 넣지 않았다.
public 두 파일은 정상 초기 빈 feed다. 실제 수집/분석 데이터 연결은 이번 범위가 아니다.

## API / Handoff

```python
from src.renderer.feed import build_feed, write_feed

feed = build_feed(notices, generated_at="2026-10-30T07:20:38.339587Z")
paths = write_feed(notices, generated_at="2026-10-30T07:20:38.339587Z")
```

build_feed는 순수 함수다. write_feed의 output_dir 기본값은 프로젝트 public 절대 경로이며 테스트에서 바꿀 수 있다.
동일 iterable을 두 함수에 전달할 경우 재사용 가능한 list 등을 사용한다(일회용 iterator는 소진된다).
반환 paths는 notices.json, metadata.json 순서다. import/생성만으로 저장/분석/수집을 실행하지 않는다.

## Limitations / Blocker

- M09 blocker 없음.
- 파일별 atomic write를 재사용하며 두 파일 전체 transaction은 아니다. notices 저장 후 metadata 저장 실패 시
  서로 다른 snapshot이 남을 수 있으며 StorageError를 호출자에게 전파한다. 자동 복구/재시도는 없다.
- 불완전/오래된 성공 결과는 배포에서 제외하고 자동 재분석하지 않는다. 별도 diagnostics 파일은 만들지 않았다.
- summary는 발췌이므로 장문 끝의 자격 조건을 포함한다는 보장이 없다. 원문 URL과 판정 근거를 함께 제공한다.
- 기존 M08 실제 API/판정 정확도 미검증 및 M05 운영 수집 제한은 그대로다.
- Git/패키지 설치/외부 호출/회사별 판단/배포 자동화/M10 이후 구현은 수행하지 않았다.

## Acceptance / Next

- [x] public/notices.json 및 public/metadata.json 생성.
- [x] 현재 유효한 관련 공고만 배포하고 실패/대기/irrelevant 제외.
- [x] 공통 schema version/필수 필드 및 독립 JSON 읽기.
- [x] 본문 장문 미배포, deterministic data/order/formatting 및 시각 주입.
- [x] 전체 unittest 회귀 통과와 결과/상태 문서 갱신.

다음은 **V2 M10 — Central End-to-End Pipeline**이다. 이번에는 src.main을 변경하지 않았다.
M10에서 저장된 전체 Notice snapshot을 명시적으로 공급해야 한다. M07 관측 batch만으로
저장소/공개 feed를 대체하여 미관측 기존 공고를 잃지 않도록 한다.
