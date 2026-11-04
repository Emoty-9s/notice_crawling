# Performance preview and explicit technical tags — 2026-11-03

## Changes

- Preview table now has only 번호, 연도, 관리번호, 실적명, 고객, 기술분야, 업무유형,
  in that order. 번호 is the preview sequence, not the original sheet row.
- Extended the existing model taxonomy config with specific 전기자동차 and 배터리
  tags, their source aliases and existing parent categories. No separate industry
  taxonomy or matcher scoring system was introduced.
- Explicit source mentions are mapped independently before embedding inference.
  `전기자동차 배터리팩` yields primary `전기자동차`, secondary `배터리`, and the
  cell displays `전기자동차 · 배터리`. The original model's competing top1/top2
  margin cannot veto this source-backed evidence. Other unrecognized text still
  uses the offline semantic classifier and may abstain.
- Reproduced the previous short-input problem: `전기자동차` had top1/top2 cosine
  margin 0.009391, below the 0.010 gate, and was rejected. Its top1 broad category
  was also electrical/electronic rather than automotive. Source-backed specific
  tags now take precedence, without globally lowering ambiguity thresholds.
- Tags preserve source spelling as evidence and provenance `deterministic_mapping`;
  confidence is null rather than an invented AI percentage. Existing Excel/user
  fields are protected even on forced analysis.
- Both tags and their existing parent categories reach matcher keywords; scoring
  rules remain unchanged. Both tags are retained in searchable_text and enrichment
  metadata. User edits replace stale tags; multiple user tags accept `·` or commas.
- Existing unclassified records are repaired through 미분류 실적 분석. Records with
  previous nonempty AI classifications can use 기존 AI 결과도 갱신. No automatic
  dashboard-time model execution or overwrite of explicit/user fields was added.

## Validation

- Targeted enrichment suite: 32 tests / 30.644 seconds / OK.
- New regressions: Korean/English/compound EV+battery inputs, evidence ordering,
  English alias boundaries, model-unavailable fallback, source/user protection,
  user multi-tag replacement, exact seven preview values, DB reload/reanalysis,
  raw_source preservation and matcher keyword propagation.
- Existing held-out broad-category/work classification gates: PASS (28 cases).
- Final frozen EXE: exit 0, seven preview columns verified; EV/battery tags and
  their actual Treeview cell text verified; 5 rows saved, forced reanalysis saved,
  separate process restart retained 5 rows, matcher returned 5 positive results.
  Source bytes unchanged, protected/explicit changes=0, external calls=0.
- Native file-picker return was injected by the existing opt-in frozen test
  harness. Native picker clicks and a new screenshot review remain unverified.
- Distribution size: 239,887,863 bytes. EXE SHA256:
  `95708f845ec99be59474caa18f5f4215a350fc1fab023f0682d54f5adca07f9b`.
- Full unittest suite: **552 tests / 79.566 seconds / OK**.

No commit/push. Earlier local AI measurements are historical; this document
records the newer preview/tag build.
