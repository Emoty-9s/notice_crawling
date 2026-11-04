# Public prefilter and independent local A/B analysis

## Central and history

Central runtime imports no Gemini client/queue and no ONNX runtime. It collects
the same seven sources (three-page cap, unchanged KISTA/RIPC transport), merges
observation history and evaluates the existing deterministic prefilter. Active
or unknown-deadline CANDIDATE and REVIEW rows publish immediately. CLEARLY_UNRELATED
and explicitly expired rows remain in history. No AI key, request budget, quota
or retry time affects publication. Historical Gemini and analysis queue fields
remain unchanged except independently versioned prefilter fields. They are not
new local judgments. The archived default Gemini transport raises PROVIDER_RETIRED;
injected offline clients/parsers remain for historical regression coverage.

The checked-in site flags and cron 17 22 UTC are unchanged. Actions alone builds
the operational config. One workflow writer, OS lock, state validation, atomic
Notice snapshot and always-upload of valid state remain. Restore picks the latest
artifact by creation timestamp. Existing artifact retention remains 90 days.

## Feed v3 and migration

v3 explicitly changes publication semantics. Fields: notice_id, source_id,
institution, title, URL, published/apply dates, summary, full cleaned public
content_text, prefilter status/reason/policy, internal content_hash, computed
public_content_hash, observation/update timestamps and producer is_new. Work
scope, recruitment and qualification evidence remain in the actual body rather
than invented fields. Emails, phone numbers and labeled contact names are masked;
qualification clauses remain. No local company records/results/cache can be in
this explicit publication allowlist. Metadata keeps generated_at and notice_count.

Old v2 executables reject v3 rather than misinterpret candidates as AI-approved.
Pages explains the update requirement. New consumers accept validated v2/v3
pairs and reject mixed versions. A always uses public title/summary/body rather
than old Gemini classification. V3 public hashes are recomputed during validation.
Old valid v2 snapshots remain usable when offline; they do not authorize A.

## A: public-work relevance and separate qualifications

Versioned work profiles live in src/local_client/work_profiles.py. The unchanged
E5 query-prefix/tokenizer/truncation/normalization contract is reused. Real duty
expressions are extracted before embedding, reducing dominance by product names.
Positive work profiles and unrelated-scope profiles are compared using cosine;
there is no arbitrary global cutoff and no claim of calibrated probability.
HIGH requires actual duty context plus stronger positive-profile similarity.
Industry names, generic IP labels, event goals and selection-result notices alone
cannot promote a row. Unclear tasks, beneficiary programs and unclear roles stay
REVIEW. Explicit manufacturers and ordinary trainee recruitment are excluded;
mixed genuine IP consulting/training remains reviewable.

Qualifications are independently EVIDENCE, CHECK_REQUIRED or EXPLICIT_EXCLUSION.
Professional services alone never certify eligibility. Public sample calibration
demoted IP event operation, educational program and beneficiary/event-goal cases
that initially looked too similar. This is conservative triage, not legal advice
or an independently measured classifier accuracy.

A has no company DB argument or SQL access. Its key is notice ID + computed public
input hash + work policy/profile version + unchanged model version. Work cache
is cache-path.work.json, exclusively local. Hash, model or policy changes re-evaluate;
performance CRUD, DB path, customer, technical tags and matcher results cannot.
Only validated successful cache entries bypass model loading. Failures are REVIEW/
UNAVAILABLE with a fixed diagnostic, never exclusion or a fabricated success.

## B: local technical comparison and unchanged matcher

B runs only when matching is expanded. It removes shared work expressions from
public titles/body and actual performance project names, technical fields,
descriptions and keywords. It uses actual E5 vectors, not generated synonyms.
Management IDs/customer names/attorneys/notes are not semantic inputs. All stored
technical fields are represented by the existing technical_field serialization;
no company database schema migration is performed.

B key: notice ID + public hash + technical policy/lexicon fingerprint + model
version + performance-data revision. Its separate cache is cache-path.technical.json.
Add/edit/delete changes that revision and invalidate B; A is untouched. B displays
technical similarity comparisons separately from existing matcher recommendations.
The matcher file, formula, weights, tie-breaking and original recommendations are
unchanged, with no blended score. V3 uses a deterministic public-work adapter for
required matcher fields. V2 regression fixtures preserve original inputs to prove
old exact scores and ranking remain unchanged. Failure leaves the existing matcher
available and A unchanged.

## UI and runtime

Dark Night, source cards, upload selection, management, offline taxonomy and local
DB are retained. A starts after sync in a worker thread, which supervises the
existing spawn-only model process architecture; heavy model imports stay outside
Tk's process/GIL. B is independently spawned when expanded. Both children deny
socket/DNS/HTTP audit events and report observed network attempts. Source GitHub
sync is a separate legitimate network path. Closing cancels workers, bounded
supervision joins/terminates processes and avoids retaining model sessions.

Lists show work grade, qualification status, local analysis state and separate
names for work cosine / technical cosine / original matcher points. REVIEW is
visible by default; explicit excludes have a visibility checkbox. Source-card
counts and list filtering use the same displayed collection.

## Validation commands

```
.venv/Scripts/python.exe -m unittest discover -s tests
.venv/Scripts/python.exe -m tools.eligibility_projection_smoke
.venv/Scripts/python.exe -m tools.prefilter_audit --data-dir .run/history-live-readonly
powershell -NoProfile -ExecutionPolicy Bypass -File build_windows.ps1
dist/notice_crawling/notice_crawling.exe --local-analysis-smoke-report .run/local-ab-exe.json
powershell -NoProfile -ExecutionPolicy Bypass -File tests/run_final_exe_checks.ps1
```

All smoke inputs are synthetic or read-only public notices. The explicit A/B smoke
uses temporary synthetic DB/cache, actual Tk commands and actual ONNX subprocesses.
It proves zero vs 100 performance independence, lazy B, edits/deletion, original
matcher equality, cached A reuse without model and main-thread heartbeat below
350ms. Native coordinate/picker clicks are distinct and are not claimed.

## Verified local results (2026-11-04)

Full unittest: 656 PASS, failures 0, errors 0, 215.074 seconds. Central/public/
local projection smoke: history 6, published 4, provider calls 0 on both runs,
NEW true then false. Actual read-only public audit: history 244, publishable 83
(CANDIDATE 19 / REVIEW 64); local ONNX A HIGH 2 / REVIEW 81 / EXCLUDE 0, all 83
qualifications CHECK_REQUIRED. Original history SHA unchanged, company DB unused.

Fresh build and frozen A/B smoke PASS: actual model subprocesses, observed network
attempts 0, A identical with 0/100 performances and after CRUD, lazy B updates,
unchanged matcher results and cached A reuse when the encoder is unavailable.
Battery example technical cosine 0.893478 versus food-packaging 0.805209; these
are illustrative measured similarities, not accuracy or eligibility percentages.
Frozen Tk max heartbeat gap 218.71ms. Synthetic upload/management/restart PASS:
5 rows -> deselect 2 -> save 3 -> edit -> delete 1 -> restart with 2. Integrity ok,
foreign-key violations/orphan metadata/network inference attempts all 0.

Local HTTP v3 feed with the actual 83 public notices: new EXE UPDATED/UNCHANGED,
83 cards, seven source cards, detail/accordion/seen preserved and no company DB
created. All 83 public notices also completed actual frozen ONNX A analysis in
3.772 seconds (HIGH 2 / REVIEW 81), subprocess observed network calls 0, active
sessions after 0. Old v2 EXE fetched v3 metadata and stopped with SyncError before fetching
notices, confirming safe rejection. Native computer-use initialization failed
with Node runtime path OS error 3; actual Tk command smoke is verified separately.

EXE: dist/notice_crawling/notice_crawling.exe. SHA256:
A2AE10A1CE69A5B1892521275C539A3C37D3CA30EC38601DC3243ED46F09E2CD.
Live Actions run/deployment evidence is reported with actual IDs in the session;
no operational secrets, model choice or company database were changed.
