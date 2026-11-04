# Offline local performance enrichment — 2026-11-03

## Status and scope

Implemented in the local upload/preview/database path. Existing central scraper,
Actions, central Gemini, Pages, state/feed contracts and deterministic matcher
scoring are unchanged. The pre-existing uncommitted retention/upload work has
been retained. No production company data was used, copied or transmitted.

The final distribution is under `dist/notice_crawling/`; distribute the whole
directory, including `_internal`, models and license notices.

## Selected model and licensing

- Model: **intfloat/multilingual-e5-small**, E5/Microsoft research team, official
  intfloat distribution on Hugging Face. Immutable selected revision:
  `614241f622f53c4eeff9890bdc4f31cfecc418b3`.
- Official model card: <https://huggingface.co/intfloat/multilingual-e5-small>.
  It declares MIT, lists Korean (`ko`) and English (`en`), and documents 100
  languages and 384-dimensional embeddings. The official non-retrieval
  `query: ` prefix, masked mean pooling and L2 normalization are used.
- License verified **before download/selection**: official model card MIT and
  upstream <https://github.com/microsoft/unilm/blob/master/LICENSE>. Commercial
  use/redistribution is permitted under MIT with copyright/permission notices.
  A copy of that notice and the original model card accompany the resources.
- FP32 ONNX original: **470,268,510 bytes (470.27 MB)**.
- Official quantized artifact: `onnx/model_qint8_avx512_vnni.onnx`,
  **118,346,824 bytes (118.35 MB)**, distributed locally as `model.onnx`.
  It is an ONNX graph executed by CPUExecutionProvider, not an AVX512 executable.
  Actual operation was verified on an ordinary Intel i3-10105 Windows CPU.
- Tokenizer: `tokenizer.json`, **17,082,730 bytes (17.08 MB)**.
- Entire model resource directory, including config/model card/licenses/notices:
  **136,694,858 bytes (136.69 MB / 130.36 MiB)**.
- Runtime: **ONNX Runtime 1.23.2 CPU**, tokenizers **0.22.2**, NumPy **2.2.6**.
  CPU inference is limited to two intra-op threads, one inter-op thread;
  tokenizer parallelism is disabled. No GPU provider or GPU dependency.
- Tokenizers runtime is Apache-2.0. ONNX Runtime is MIT. Runtime/package license
  and third-party notices, including NumPy/FlatBuffers/Protobuf notices, are
  included under `models/performance_classifier/notices/`.
  Sources for missing wheel notices:
  <https://github.com/huggingface/tokenizers/blob/v0.22.2/LICENSE> and
  <https://github.com/google/flatbuffers/blob/master/LICENSE>.
- Weights and tokenizer hashes are checked at load; all source artifact hashes
  and sizes are recorded in `resources/models/performance_classifier/manifest.json`.
  Missing/corrupt resources fall back locally; they never trigger a download.
- `tools/fetch_performance_model.py` is an explicit **build-time only** downloader
  with a pinned revision and license check. It is not imported by the runtime.
  Build preflight checks hashes/licenses offline and fails if resources are absent.

## Runtime, privacy and responsiveness

File parsing and enrichment run in a spawned local process. An I/O thread
relays progress/results over a local OS pipe to the existing Tk after() queue.
The child is joined/closed after returning a preview; no model process remains
resident. No model/runtime import occurs on dashboard startup or DB reload.
Windows/PyInstaller spawn uses the standard multiprocessing freeze_support.

This design was verified after discovering a roughly one-second event delay
when first importing native readers/runtime from a background thread. The final
process design's final actual frozen EXE maximum heartbeat interval was
**201.57 ms** during its import/edit/reanalysis/save test (224 heartbeat ticks,
with the full unittest suite also running). An isolated earlier run measured
44.30 ms. These are measured event-loop intervals, not a latency guarantee.

The analysis child installs a network audit guard rejecting socket connection,
DNS and urllib requests. It returns only safe counters, not cell text, as runtime
statistics. The frozen test additionally blocks the UI process's HTTP transport.
ONNX telemetry events are explicitly disabled before constructing a session.
The implementation never calls Tokenizer.from_pretrained, a hub client, external
inference, Gemini or OpenAI. Original company rows travel only through local
process memory/OS pipes and the selected private SQLite DB.

Normal dashboard startup retains the existing GitHub feed check. For an entirely
network-free launch, use the existing `--offline` flag. The upload/local-model
path itself does not request the internet in either mode. No user DB/cache,
spreadsheet or private configuration is bundled.

## Extraction, inference and source priority

Priority: user > explicit Excel/alias/parser/heuristic > local_model > unknown.
Existing explicit values are never replaced, even by a forced reanalysis.

- Model-writable fields are explicitly allowlisted to project_name,
  technical_field, work_type and keywords.
- management_id/client/start_date/end_date/year/amount are never model-writable.
  Missing values remain None in normalized data. The legacy Performance model's
  non-null client string is adapted as empty string, preserving the DB contract.
- Project inference is **extractive**: only a confident selection of an existing
  source cell, never a generated title. Explicit and short original titles stay.
- Description/raw_source are original input, not generated summaries. Multiple
  description columns are joined without rewriting their meaning. AI does not
  change raw_source; DB migration/reanalysis also leaves stored raw_source bytes
  untouched. Before/after protected/explicit field counters verify this.
- Technical classification uses actual embedding cosine comparison against 20
  broad Korean/English category descriptions. There is no industry-keyword
  lookup classifier. Task-name removal based on existing matcher terminology
  separates the research subject from the service being performed.
- Secondary technical candidates within 0.045 cosine of the first and above
  the acceptance floor are retained with scores in metadata. Ambiguous primary
  classification may still be 미분류 while these candidates remain reviewable.
- Work types reuse the existing matcher's four category groups through canonical
  values: 특허분석, 기술사업화, 특허출원, 분쟁대응. Original task/action spans
  help the model focus on work rather than industry. Missing service evidence
  cannot turn an industry noun into an unmentioned service.
- Keywords are original source substrings ranked by model similarity, max 8,
  deduplicated and stripped of IDs/currency/dates/generic stop words. Existing
  explicit keywords are protected. The matcher adapter may add accepted primary
  taxonomy components, with max 15 matcher keywords; this does not change scoring.
- searchable_text combines source/business text and normalized fields/keywords.
  It is not AI-authored prose. Original ID/amount data remains in raw_source.

## Confidence and review

Similarity is **not a calibrated probability**. The UI displays actual cosine
and top1-minus-top2 margin, including both technology and work scores. Explicit
values display 원본; edited values display 사용자, not a stale AI confidence.

Acceptance requires cosine >= **0.79**, margin >= **0.010**, and a lead >=
**0.012** over unrelated/unknown reference descriptions. Work types also require
source task evidence. Automatic application requires cosine >= **0.84** and
margin >= **0.035**. Other accepted suggestions are 확인 권장. Rejected results
are 미분류/확인 필요; no forced nearest category is stored as an accepted result.
Scores/runner-up/unknown cosine/rank/margin/decision are preserved in ai_evidence.

Stored provenance: field_sources, field_confidence, ai_model_version (model
revision/quantization + taxonomy version), normalization_version,
review_required, technical_fields and ai_evidence. It is in the additive
`performance_enrichment_v1` table; base Performance columns/version stay v1.

## User edits, existing data and model lifecycle

Preview shows technology/work, origin, real scores and review status. Selecting
a row opens editable technology/work controls. `수정 적용` records source=user.
User edits survive save/restart/reimport and forced model reanalysis. Unsaved
edits must be saved before switching to existing-DB reanalysis.

`미분류 실적 분석` loads existing records read-only, fills eligible empty fields
and previews before save. `기존 AI 결과도 갱신` explicitly opts into replacing
prior AI outputs; it never replaces user/Excel/parser/legacy explicit values.
Same-fingerprint imports restore previously approved model/user values without
rerunning complete analyses. Still-unclassified values remain eligible.
Optimistic record+metadata revisions reject stale saves after concurrent edits;
later edits through the existing DAO also outrank an old metadata snapshot.
Duplicate reimports do not silently write cached user values back to the DB.

Progress uses completed/total counts; cancel is observed between batches and
returns a deterministic preview without partial AI results. Model/session errors
return the exact local fallback notice. A helper-process failure also preserves
the deterministic import path. Production never creates sample/fixture rows.

## Quality evaluation

All labeled examples are synthetic and live under tests. The initial 30 cases
were a **development** set used to identify category/task contamination and
refine input views. Final development result: technology top1/top2 100%, known
work-type accuracy 87.5%, unknown technical precision/recall 100%.

A separate **28-case validation set** was created after selecting the approach
and thresholds. No prototype/threshold changes were made based on its results.
It includes 23 technical cases (all 20 broad groups, English/mixed language,
description-only input) and 5 unknowns; 22 cases have a known work type.

- Technical top1: **23/23 (100%)**.
- Technical top2 candidate rank: **23/23 (100%)**.
- Work type: **22/22 known (100%)**, **28/28 including unknown (100%)**.
- Unknown technical precision: **5/5 (100%)**, recall **5/5 (100%)**.
- The explicit quality gate passed: top1 >=85%, top2 >=90%, work >=80%, unknown
  precision >=90%, unknown recall >=80%.
- User protection and zero extraction hallucinations are separate invariant
  tests, not inferred from classification accuracy.

These are small, clear, manually labeled test sets, not an independently sampled
corporate benchmark or an accuracy guarantee for arbitrary real workbooks.
Sparse/overlapping/out-of-taxonomy rows may abstain and still require review.
The development work-type score includes conservative abstentions as errors.

## Performance measurements

Machine: **Intel Core i3-10105 @3.70GHz, 4 cores/8 logical CPUs**, Windows x64.

300-row synthetic workload (all 28 validation subjects cycled, including keyword
extraction), same ONNX CPU engine: **9.690 s wall**, **17.562 CPU seconds**,
max working set **448.46 MiB**. Completed 300/300, no warning, external calls=0.
No live model sessions remained. Idle CPU time over a 0.5-second measurement was
0.0 s. This is the engine benchmark, not a file-I/O or large-workbook benchmark.

Final frozen EXE, first preview's child: **2.789 s wall**, **3.359 CPU seconds**,
max working set **457.45 MiB**, active sessions after=0; child then exits.
The full 4-row import/edit/reanalysis/save flow took **7.544 s**, GUI process
working set **45.19 MiB**. Restart without model analysis: **0.280 s**, GUI
working set **44.03 MiB**, runtime_imported_on_start=false. Per-process peaks are
reported separately; they are not a promise of constant RAM on every machine.

## Final validation and distribution

- Full unittest: **546 tests / 78.465 seconds / OK**, including the final
  legacy title-only enrichment regression. PowerShell's redirected native stderr
  wraps unittest progress as NativeCommandError; the unittest result is OK.
- Real upload Tk smoke and unchanged dashboard Tk smoke: PASS.
- Frozen EXE offline test: **exit 0 / SUCCESS**, 4 preview/saved rows, protected
  field changes=0, explicit changes=0, model-derived technology=2 rows,
  model-derived work=1 row, keywords=3 rows. The intentionally ID-only row stays
  unclassified. Leading zeros/source bytes preserved; no preview DB write.
- User editor PASS; forced reanalysis protects user values; 4 updates saved.
- Separate EXE restart: **exit 0 / SUCCESS**, 4 rows remain, user/provenance
  preserved, 4 positive matcher results, no model load at startup.
- UI and analysis process external-call counters: **0**. HTTP is actively blocked,
  not merely presumed offline. Model loads from bundled resources.
- Final distribution: **239,884,623 bytes (239.88 MB / 228.77 MiB)**.
- Final EXE SHA256:
  `b2b600e7f87e7d9c3dec57af27cf1688bcd956dc5fb583ef67892666e744d77e`.
- Frozen PYZ has no torch, transformers, huggingface_hub or hf_xet modules;
  distribution has no DB, SQLite, XLSX, XLS or CSV company/test data files.

The native Computer Use helper remains unavailable (missing native pipe). The
actual frozen executable and actual XLSX/preview/editor/save/matcher/process
restart were tested; file-picker return is injected in the opt-in test harness.
Actual native picker clicks and a new visual screenshot review remain unverified.

Build/test commands:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe tests/evaluate_local_model.py --fixture heldout.json --check
.\.venv\Scripts\python.exe tests/benchmark_local_model.py
.\.venv\Scripts\python.exe tests/ui_upload_smoke.py
.\.venv\Scripts\python.exe tests/ui_dashboard_smoke.py
powershell -NoProfile -ExecutionPolicy Bypass -File build_windows.ps1
.\.venv\Scripts\python.exe tests/prepare_ai_exe.py
powershell -NoProfile -ExecutionPolicy Bypass -File tests/run_ai_exe_checks.ps1
```

Company data never goes into the tests. Generated test workbooks/DBs stay under
ignored `tests/fixtures/performance_enrichment/runtime`; reports under ignored
`.run/` contain counts/metrics only. Resources are read-only application files,
separate from the user's default LOCALAPPDATA DB/cache.

## Changed files for local AI work

- New: `src/local_client/local_model.py`, `enrichment.py`, `analysis_worker.py`.
- Extended: `upload.py`, `upload_store.py`, `upload_ui.py`; no matcher edits.
- New model config/manifest/license/notices under
  `resources/models/performance_classifier` (large weights/tokenizer are ignored
  in Git and acquired explicitly at build time; present in the distribution).
- New build helpers `tools/fetch_performance_model.py`,
  `prepare_model_distribution.py`; extended build script/runtime requirements.
- Extended frozen upload checker/entry with process freeze support.
- Added `tests/test_enrichment.py`, labeled JSON fixtures, quality/benchmark/input
  scripts and frozen checker runner; extended upload Tk smoke.
- Updated README, Windows distribution README, ignore rules and progress docs.

No new commit/push. Existing HEAD: `995ab1b51954e83d3536b82a27e76a0d1267665a`.
