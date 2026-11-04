# Local title/phrase multilabel classification — 2026-11-03

Implementation and isolated EXE checks are complete; **real-user DB evaluation
is not complete**. No business database was found at the project default or host
Windows default. Workspace DBs found outside tests were prior validation inputs,
not accepted as real-user data. The user has been asked for the actual DB path.
There are no invented real-data counts or anonymized company fixtures.

## Current policy

- Keep multilingual-e5-small INT8 ONNX, CPU runtime, offline-only execution and
  existing separate analysis process. No new model, API or runtime dependency.
- Remove technical-field top1/top2 margin rejection. Margin is retained solely
  as evidence. The existing work-type taxonomy and its rule remain unchanged.
- Encode title, independent title nouns/ngrams, and description phrases. The
  taxonomy has a few representative Korean examples and its existing English
  description per broad label. Unseen source phrases are classified semantically,
  not through a comprehensive hand-written industry keyword dictionary.
- Full-title primary threshold 0.84; source phrase threshold 0.89; nontechnical
  reference lead 0.025. A full title's additional categories require 0.91/0.93.
  Other independent phrases can each supply their own top category. Additional
  broad fields require at least 0.86. There is **no margin veto**.
- Title-supported fields precede description-only evidence. Description-only
  additions require 0.94 when the title supplies a subject, or 0.89 when it does
  not. Direct source aliases remain stronger than model-only evidence.
- Both broad categories (`technical_fields`) and specific source phrases
  (`technical_tags`) are separately persisted, each capped at 3. A primary broad
  string remains in legacy `technical_field`. Additional extracted phrases and
  top5/evidence remain in local metadata, including phrases absent from taxonomy.
- The seven-column preview remains unchanged. It displays detailed tags first;
  the details pane includes both levels and actual scores/provenance.
- User edits and meaningful original Excel fields remain protected. Legacy/Excel
  literal 미분류 is missing information and can be filled; a user's deliberately
  selected 미분류 remains protected. v2 tag-as-field metadata adapts in memory and
  is persisted through the existing explicit Save action.
- Raw source, IDs, client, dates, year and amount remain immutable to the model.
- Both broad labels and detailed tags reach the existing matcher keyword adapter.
  Explicit existing keywords are preserved; scoring rules are unchanged.

## Diagnosis without leaking company titles

`tools/diagnose_performance_fields.py` defaults to read-only DB evaluation.
The local GUI (`--view`) shows titles, top5, cosine, margin, direct terms and
phrase extraction results. Titles/raw rows are never printed or included in the
summary file. Stdout and ignored `.run/private-diagnostics/summary.json` contain
counts only. Network attempts are blocked and counted.

Reasons: LOW_SCORE, LOW_MARGIN (legacy only), NO_TEXT, NO_LABEL_MATCH, MODEL_ERROR.
An additional NOT_ANALYZED_OR_LEGACY_DATA distinguishes missing analysis from a
false claim of model rejection. Stored rejection evidence is preferred when
available; a replay is marked `reason_basis=replayed_legacy_rule`, because INT8
scores may vary slightly with batch/padding. New policy evidence never rejects
because of LOW_MARGIN. The complete model error message is not logged.

```powershell
.\.venv\Scripts\python.exe tools/diagnose_performance_fields.py --db "actual DB path" --view
# Optional explicit save, with a local SQLite backup first:
.\.venv\Scripts\python.exe tools/diagnose_performance_fields.py --db "actual DB path" --apply --view
```

Real data status:

- BEFORE UNCLASSIFIED: **not measured / DB path required**.
- AFTER UNCLASSIFIED: **not measured / DB path required**.
- NEWLY CLASSIFIED: **not measured / DB path required**.
- REAL DB SAMPLE CHECK: **not performed**. Real-title manual labeling/anonymized
  regression cannot be claimed without the actual records.
- No automatic production DB writes have been made for this task.

## Validation

- The six user-specified regression cases are in
  `tests/fixtures/performance_enrichment/multilabel.json`. These are user-provided
  examples, **not actual anonymized company records**.
- EV/battery → automotive + energy storage; solid-state electrolyte/battery →
  battery + materials; autonomous LiDAR/sensor → automotive + electronics;
  AI medical imaging → software + medical; OLED deposition equipment →
  electronics + manufacturing. Source OLED/LiDAR phrases are retained as tags.
- Tests also cover close scores, unknown/nontechnical text, no invented food
  category for semiconductor manufacture, clear title with long administrative
  description, short AI title, protected original/user values, immutable extracted
  fields, broad/tag save/reload/forced analysis, legacy literal unknown migration,
  explicit keyword preservation and privacy/read-only diagnostic behavior.
- The prior heldout 28-case broad/work benchmark passed all gates through the
  actual new production enrichment path: technical top1/top2 100%, known work
  100%, unknown precision/recall 100%. This is a small synthetic dataset and does
  not substitute for actual company records or prove universal accuracy.
- Final full unittest suite: **565 tests / 105.858 seconds / OK**.
- Final actual frozen EXE: import/reanalysis and separate restart both exit 0;
  seven preview columns, EV/battery broad fields + detailed tags + visible cell,
  5 saves and 5 reanalysis updates, persisted tags/user override and 5 positive
  matcher results all pass. External calls=0, protected/explicit changes=0,
  original file bytes unchanged, model sessions after=0, runtime absent at startup.
- First preview child: 4.436 seconds wall / 7.062 CPU seconds / peak 460.46 MiB.
  Entire 5-row import/edit/reanalysis/save flow: 9.387 seconds; GUI peak 45.52 MiB;
  maximum measured Tk heartbeat gap 56.48 ms. This is not a latency guarantee or
  an actual company-data throughput benchmark.
- Final distribution: **239,903,270 bytes (239.90 MB)**. EXE SHA256:
  `ac7d08204399f1341ad5cc3583185216f9afcc267d5c4a2acea438044d2f3a0c`.
  No torch/transformers/Hugging Face clients or DB/Excel/CSV files in distribution.

The native Computer Use helper remains unavailable, so actual native picker
clicks/new screenshots are not claimed. The frozen Tk harness injects a picker
return and inspects the real preview/editor/save/restart paths with HTTP blocked.

## Files and contracts

New `src/local_client/technical_classifier.py`,
`tools/diagnose_performance_fields.py`, `tests/test_technical_classification.py`
and multilabel fixture. Extended enrichment/upload metadata/persistence/preview,
taxonomy example configuration, quality evaluator, frozen upload checker and docs.
No changes to deterministic matcher scoring, central scraper/Gemini/Actions/Pages.
No new commit or push. Existing HEAD: `995ab1b51954e83d3536b82a27e76a0d1267665a`.
