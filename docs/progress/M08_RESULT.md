# M08 Result

## Status

**PASS** — MILESTONES_V2.md의 M08 중앙 Gemini 공고 적합성 판정.

검증일: 2026-10-30 (Asia/Seoul). 구현·mock 테스트·저장 호환성 검증·후속 인계를 완료했다.
실제 Gemini API 연결이나 실제 공고에 대한 판정 정확도 검증을 완료했다는 의미는 아니다.

## Implemented

- config/relevance_policy.yaml: 특허법인/특허사무소가 수행기관·협력기관·입찰자·용역사로 참여 가능한지 판정하는 기준/예시/출력 schema.
- 수혜기업 전용은 기본 제외. IP 키워드만으로 수행기관 모집으로 판단하지 않는다.
- 애매하거나 본문에 근거가 부족하면 relevant=false, participation_type=불명확으로 하고 부족한 근거를 reason에 남기도록 지시한다.
- 회사 실적·수행 능력·경쟁력·지원 의사는 입력/정책에서 제외한다. 공고 내부 지시문은 신뢰하지 않는 자료로 취급한다.
- 표준 라이브러리 urllib 기반 GeminiClient: 명시적 모델/키, timeout, JSON schema 지정, 응답/오류 검증, HTTP opener 주입.
- RelevanceAnalyzer: NEW/UPDATED 분석, hash 캐시, EXISTING 무호출, batch 내 개별 Gemini 실패 격리.
- GeminiResult의 participation_type/keywords 확장 및 Notice JSON/JsonStorage 왕복. 이전 저장 형식도 읽을 수 있다.

## Files Added

- config/relevance_policy.yaml
- src/ai/gemini.py
- src/ai/relevance.py
- tests/test_gemini.py
- docs/progress/M08_RESULT.md

## Files Modified

- src/core/models.py: 새 결과 필드 및 keywords 불변성/JSON array 직렬화.
- src/core/storage.py: 이전/현재 Gemini schema 호환 검증.
- tests/test_models.py: 확장된 JSON 필드 계약 반영.
- .env.example: 실제 호출 시 사용할 환경변수 이름/설명만 추가.
- docs/progress/CURRENT_STATE.md: M08 상태 및 V2 후속 순서 반영.

## Tests

검증 명령:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

실제 결과: **192 tests, OK**, 실패/오류 0, exit code 0.
M08 신규 26개 + 기존 166개 회귀 테스트가 통과했다. 실제 API/사이트 요청은 없다.

- mock HTTP 요청의 입력 8필드, schema, User-Agent, timeout, 키 헤더/URL 분리를 확인했다.
- relevant true/false/불명확, participation_type/keywords/hash/분석 시각 저장 및 JSON 왕복을 검증했다.
- 잘못된 JSON, 중복 키, 비표준 상수, 누락/추가 필드, 잘못된 bool/keywords를 거부한다.
- 차단/중단된 응답, timeout, API 오류, 설정 누락 및 비정상 timeout을 검증했다.
- 동일 ID/hash의 중복 호출 방지, 저장된 성공 캐시 재사용, 다른 ID 분리, M07 UPDATED hash 변경 재분석을 검증했다.
- EXISTING은 분석 상태와 관계없이 호출하지 않으며 미분석은 PENDING으로 표시한다.
- 한 공고의 실패 후 다음 공고 성공, 재분석 실패 시 이전 결과 보존, 실패 시도 중복 방지를 검증했다.
- 오류/로그/콘솔/저장 JSON에 API key가 포함되지 않는지 검증했다. 허용되지 않은 오류 코드도 고정 코드로 치환한다.
- 임시 저장소에서 새 구조 round-trip, 이전 8필드 로딩/원본 파일 비변경, 부분 신규 schema 거부를 검증했다.

## Decision / Cache Contract

입력은 institution/title/category/published_at/apply_start/apply_end/content_text/url의 8개뿐이다.
출력은 relevant(bool), category(str), participation_type(str), reason(str), keywords(array[str])의 5개 필드만 허용한다.
빈 설명/참여 유형은 허용하지 않는다. 키워드가 없으면 빈 array를 사용할 수 있다.

| 입력 상태 | 처리 |
| --- | --- |
| 완전한 SUCCESS + analyzed_content_hash == content_hash | 기존 성공 결과 재사용 |
| NEW, 유효한 성공 캐시 없음 | 분석 |
| UPDATED, hash 변경/유효한 성공 캐시 없음 | 재분석 |
| UPDATED, 같은 hash의 완전한 성공 결과 있음 | 재사용(제목 등 메타데이터만 변경된 경우 포함) |
| EXISTING | API 무호출, 기존 결과 유지; NOT_ANALYZED만 PENDING으로 표시 |
| 같은 세션의 동일 notice_id/content_hash | 성공/실패 포함 앞선 시도 재사용 |

캐시 key는 (notice_id, content_hash)다. 서로 다른 공고가 같은 hash를 가져도 결과를 섞지 않는다.
중앙 실행에서 analyzer 한 인스턴스를 공유한다. 성공은 Notice에 저장되어 새 인스턴스에서도 재사용한다.
동시 프로세스/분산 실행 사이의 중복 호출 잠금은 구현하지 않았다.

SUCCESS 시에만 analyzed_content_hash/analyzed_at을 현재 성공 값으로 갱신한다.
실패 시 이전 판단/참여 유형/키워드/성공 hash/시각을 보존하면서 FAILED/PENDING으로 변경한다.
따라서 이전 판단을 최신 성공으로 오인하지 않도록 상태와 분석 hash를 함께 확인해야 한다.

## Failure Contract / Secrets

- timeout/네트워크 오류/HTTP 429·5xx/키·모델 설정 누락 → PENDING.
- malformed JSON/출력 schema 오류/차단·불완전 응답/기타 API 오류·예상 밖 분석 오류 → FAILED.
- 공고별 오류는 analyzer.errors와 고정 로그 코드로만 진단한다. 원문 API 오류/공고 본문/키를 출력하지 않는다.
- 키는 x-goog-api-key 헤더에만 사용하며 URL에 넣지 않는다. 리디렉션에 키를 전달하지 않는다.
- 실패한 공고도 Notice를 반환하고 다음 공고를 계속 처리한다. KeyboardInterrupt/SystemExit은 삼키지 않는다.
- 자동 재시도/스케줄링은 없다. 새 analyzer의 NEW/UPDATED 호출은 실패 건을 다시 시도할 수 있으나 EXISTING은 항상 무호출이다.
- 잘못된 Notice 타입 등 호출 계약 오류는 프로그래밍 오류로 취급한다. 공고별 Gemini 실패와 구별한다.

## Manual Verification / Design Decisions

- 시작 전 V2 M08, CURRENT_STATE, M07_RESULT, models.py, diff.py 및 관련 테스트를 읽었다.
- API REST 형식은 [Google 공식 structured output 문서](https://ai.google.dev/gemini-api/docs/generate-content/structured-output?hl=en)를 확인했다.
  generateContent 요청에 generationConfig.responseFormat.text의 mimeType/schema를 지정한다.
- policy 파일은 JSON 문법의 YAML 1.2로 저장하여 표준 json 모듈로 읽는다. 임의 YAML 문법 지원을 추가하지 않았다.
- GEMINI_API_KEY/GEMINI_MODEL은 프로세스 환경변수 또는 GeminiClient 생성자 인자로 명시한다.
  .env 자동 로딩/기본 모델 선택/모델별 무료 quota 가정은 없다. unit test에는 두 설정이 필요 없다.
- 모델의 기존 score는 저장 호환성용으로 유지하지만 M08 출력/판정에는 사용하지 않으며 신규 분석은 null이다.
- keywords는 모델 내부 tuple로 불변성을 유지하고 JSON에서는 array, 미상 기존 값은 null이다.
- JsonStorage는 기존 8필드 또는 현재 10필드 Gemini 객체만 허용한다. 부분 추가 schema는 오류다.
  이전 파일은 load만으로 다시 쓰지 않으며 새 필드 값은 None이다.
- scraper/normalizer/diff/원본 fixture/sites 설정/실제 data 파일은 수정하지 않았다.
- Git/패키지 설치/실제 Gemini 호출/회사별 로직/M09 이후 구현은 수행하지 않았다.

## Acceptance Criteria

- [x] 중앙 업계 참여 가능성 판정 기준과 수혜기업 제외 원칙이 명확함.
- [x] 구조화 결과/참여 유형/키워드 및 성공 분석 hash 저장 가능.
- [x] EXISTING 무호출 및 동일 hash 재호출 방지.
- [x] 변경 hash 재분석과 기존 분석 이력 보존.
- [x] 개별 Gemini 오류가 다음 공고 분석이나 저장용 Notice 반환을 중단시키지 않음.
- [x] 실제 API 없는 unit test 및 전체 회귀 검증.
- [x] 결과/현재 상태 문서와 후속 인계 완료.

## Known Issues / Blocker

- M08 unit 구현 기준 blocker 없음.
- 실제 API 인증/모델별 schema 지원/quota/현장 판정 정확도는 미검증이다. 실호출 검증은 unit test와 별도로 수행해야 한다.
- policy/모델 변경에 따른 캐시 자동 무효화, 재시도 스케줄, 다중 프로세스 잠금은 없다.
- 기존 SUCCESS에 새 필드가 없으면 완전한 M08 캐시로 인정하지 않는다. 그래도 EXISTING은 자동 호출하지 않고 기존 이력을 유지한다.
- content_hash 정확성은 M03/호출자 책임이다. M07이 본문 변경을 보고하더라도 잘못 재사용된 hash를 M08에서 교정하지 않는다.
- 본문에 없는 첨부/외부 링크 자격 조건은 추론하지 않는다. 기존 M05의 표본/네트워크 제약은 유지된다.

## Next Milestone Notes

다음은 **V2 M09 — Public Notice Feed JSON**이다. 이번에는 feed/요약/배포 파일을 만들지 않았다.
후속 단계에서는 SUCCESS 여부뿐 아니라 현재 hash에 맞는 완전한 결과인지 확인하여 오래된/불완전한 분석과 구별해야 한다.
V2 M10에서 registry → diff → analyzer → storage/feed를 명시적으로 연결한다.
M07 batch 결과만 전체 저장소로 덮어쓰지 말고 미관측 기존 공고를 보존해야 한다.
로컬 실적 DB/매칭/지원 의사 판단은 이후 로컬 마일스톤 영역이다.
