# Closed technical taxonomy + 소부장 — 2026-11-03

## Authoritative allowed labels

The sole vocabulary is `resources/models/performance_classifier/taxonomy.json`
`technical`. Its original twenty entries remain unchanged; only 소부장 is added.
`미분류`/empty are absence states, not additional technical candidates.

1. AI / 소프트웨어
2. 데이터 / 클라우드
3. 반도체
4. 전기 / 전자
5. 통신 / 네트워크
6. 로봇 / 자동화
7. 기계 / 제조
8. 자동차 / 모빌리티
9. 이차전지 / 에너지저장
10. 에너지 / 환경
11. 소재 / 화학
12. 바이오 / 제약
13. 의료 / 의료기기
14. 식품 / 농업
15. 건설 / 인프라
16. 항공 / 우주
17. 해양 / 조선
18. 콘텐츠 / 미디어
19. 지식재산 / 특허
20. 연구개발 / 기술사업화
21. 소부장 — added

## Enforcement

- Technical primary is a candidate, and `technical_fields` contains at most three
  unique candidates. AI outputs, original import values, user selections, fresh
  inserts, duplicate user edits and reanalysis saves pass the same vocabulary
  validation. Four selections or unknown strings are rejected, not silently kept.
- The UI table and selection list use candidate names only. It no longer shows
  title phrases as technical fields. The seven requested columns remain.
- Detailed source terms such as 전기자동차, 배터리팩 and 열관리 are only supporting
  evidence/keywords/raw source. New metadata stores them under `ai_evidence`, not
  a separate technical label collection. Legacy source-term metadata is readable.
- Meaningful original fields already in the vocabulary and user-approved valid
  selections remain protected. An original unapproved Excel field can be mapped
  to candidates; the original cell remains in raw_source. Old outside-vocabulary
  user values are not silently overwritten/deleted: a new save requires a valid
  selection, and such values are not displayed as technical candidate names.
- Shared `technical_labels.py` loads the JSON vocabulary; no parallel hard-coded
  technical-label dictionary is introduced.
- Multi-label acceptance uses absolute semantic evidence. Small margin is not a
  technical abstention reason. Maximum fields is hard-capped at three.

## 소부장 classification

Representative materials/components/equipment examples are embedded in the same
offline model: sheets/films/coatings, metals/composites, fasteners/bearings/valves,
housings/connectors, manufacturing/process/assembly/inspection equipment. The
model also considers specialist-domain phrases independently. 소부장 is an
orthogonal role and can accompany a specialist candidate when its own similarity
passes the threshold. No exact-word or `장치` suffix rule assigns 소부장.

Generic component nouns do not by themselves supply an unrelated specialist
field from a weaker full-title runner-up. Independent phrase evidence is required
for those additional specialist fields when the component role is selected.

## Regression checks

| User example | Required candidates verified |
|---|---|
| 전기자동차 배터리팩 | 자동차 / 모빌리티; 이차전지 / 에너지저장 |
| 전기자동차 배터리팩 하우징 | 자동차 / 모빌리티; 이차전지 / 에너지저장; 소부장 |
| 방수시트 | 소부장 only |
| 산업용 너트 | 소부장 only |
| 반도체 증착장비 | 반도체; 소부장 (existing 기계 / 제조 can also qualify) |
| 배터리 양극재 | 이차전지 / 에너지저장; 소부장 |
| 의료용 카테터 부품 | 의료 / 의료기기; 소부장 |
| 산업용 밸브 장치 | 소부장 only |

Additional standalone checks: 특수 너트 구조, 방수시트 제조, 금속 체결부품,
정밀 가공 부품, 범용 검사장치 → 소부장. MRI 진단 장치 → 의료 / 의료기기;
태양광 모듈용 방수시트 → 에너지 / 환경 + 소부장.

These are supplied/synthetic regression examples, not real company-data claims.

## Final validation and artifact

- Full unittest: **572 tests / 125.669 seconds / OK**.
- Existing 28-case heldout quality gate: PASS; technical top1/top2, known work,
  unknown precision/recall 100% on that limited fixture set.
- Frozen EXE import/reanalysis and separate restart: **exit 0 / SUCCESS**.
- Actual Tk preview values: candidate-only check=true; automotive + battery +
  소부장 triple cell=true; seven columns verified. 6 rows saved and 6 reanalysis
  updates, then 6 records on restart. Matcher returned configured top5 results.
- Source bytes unchanged; original/protected field changes=0; external calls=0;
  user override preserved; active sessions after=0; model absent on startup.
- First preview child: 3.884s wall / 6.250 CPU seconds / peak 461.84 MiB.
  Full test flow 9.005s, GUI peak 45.81 MiB, max heartbeat interval 44.48ms.
- Native picker return was injected in the opt-in test harness. Native picker
  clicks/new screenshot review are not claimed (native helper unavailable).
- Distribution: **239,908,705 bytes (239.91 MB)**, no DB/Excel/CSV or private files,
  no torch/transformers/Hugging Face clients. Distribute the entire directory.
- EXE: `dist/notice_crawling/notice_crawling.exe`.
- EXE SHA256: `23cb442e8040158bc24e69ebe60b33124cb6c9cf00ac795935a8ad43ad37748d`.

The work-type prototype bank retains the original batch/reference composition;
the twenty-one technical labels use a separate bank. Matcher scoring, central
scraper/Gemini/Actions/Pages/state/feed are unchanged.

New files: `src/local_client/technical_labels.py`, `tests/test_closed_taxonomy.py`,
`tests/fixtures/performance_enrichment/closed_taxonomy.json`. Extended local
classifier/enrichment/upload persistence/preview, taxonomy prototypes, diagnostic
legacy-bank indexing, frozen checker/inputs, existing tests and documentation.

No commit/push. Existing HEAD: `995ab1b51954e83d3536b82a27e76a0d1267665a`.
