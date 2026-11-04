# Selected upload saving and local performance management — 2026-11-03

## Upload selection

- Leftmost 선택 column uses ☑ / ☐. A selection-cell click or Space on highlighted
  rows toggles the transient checked-index set. New previews default to all rows.
- 전체 선택, 전체 해제 and 선택 반전 apply across every page. The label reports
  checked/total and page. 1,000-row paging lets every row remain accessible without
  constructing an unbounded Tk table; checked state survives page changes.
- `save_selected` constructs a detached preview subset before calling either
  `save_preview` or `save_enriched_preview`. Unchecked rows never reach row
  persistence, and are reported as `excluded_by_user`, not failures.
- Zero selections display 저장할 실적을 선택하세요. and do not create/change DBs.
- Selection is not an UploadRow business field, schema column or persisted JSON
  flag. Existing deterministic parsing/offline AI output is retained in memory.

## Local management

- Main toolbar: 실적 업로드 + 실적 관리. Separate Dark Night list/editor windows use
  the same palette/buttons/fonts. List has seven business columns, no checkbox.
- Query loads all actual connected records, with year DESC then management ID or
  project name and stable identity. Header-click sorting and local substring
  search cover management ID/name/client/technical candidates/work type.
- Viewing an absent DB shows the empty-upload instruction and creates no file.
- Edit year, management ID, name, client, up to three of the same 21 technical
  candidates, and a readonly dropdown of existing matcher work-category values.
- Changed fields store source=user and confidence=null. Name/technical/work
  user overrides survive subsequent AI reanalysis. Raw source remains intact.
- Management ID remains TEXT, preserving leading zeros, /, - and prefixes. The
  immutable performance PK/fingerprint is not replaced; ID alone is not unique.
- Update synchronizes the existing Performance row, enrichment provenance/local
  values and uploaded normalized metadata in one transaction. Legacy records
  without upload metadata retain management ID in the existing enrichment JSON.
  Original legacy source snapshots use stable JSON-compatible value types.
- Update/delete use existing-row-only DB opens and revision checks. A missing DB
  is not recreated during an edit, and stale snapshots cannot overwrite changes.
- Delete asks confirmation before launching any mutation. Ctrl/Shift selection
  supports batch deletion with a count prompt. Parent and both known companion
  tables are removed in one transaction; FK cascades remain enabled and explicit
  cleanup supports legacy companions. Any failure rolls back all selected rows.
- UI issues no SQL. `PerformanceManagement` provides list/get/update/delete.
- Upload/save/edit/delete refresh open management lists and invalidate/recompute
  the dashboard's current matcher results, including expanded accordions/details.

## Verification

- Full unittest: **586 tests / 127.328 seconds / OK**.
- Added 14 focused service/handler tests: default checks, click/Space, clear/all/
  invert, zero-selection no-write, cross-page checks, 5 XLSX-equivalent candidate
  rows saving only 1/3/5, checked-only reanalysis, empty list, search/sort/full list
  beyond 100 records, six-field user provenance, immutable PK/raw data, leading
  zeros, candidate/work/year validation, matcher input/score refresh, multi-delete,
  forced SQL failure rollback, stale edit/batch-delete rejection and legacy IDs.
- The selection service tests use normalized preview fixtures; the frozen test
  reads a real generated XLSX from the tests directory through the actual importer.
- Final frozen EXE import/management and separate restart: **exit 0 / SUCCESS**.
  Six XLSX rows default checked → rows 2/4 unchecked → selected 4 / saved 4 /
  user-excluded 2 / failed 0. No unchecked fingerprint exists in the DB.
- Opened management window before upload: empty/no DB creation, then automatic
  list refresh to four records. Search succeeded. Edited all six fields through
  the real edit dialog, persisted 000007/PRJ-UI and six user source markers.
- Expanded matcher refreshed the edited project without reopening. Declined
  deletion left the record intact; confirmed deletion removed it immediately from
  the list and matcher. Restart retained three records, edit values, and deletion.
- Both companion tables have **0 orphan metadata rows**. Raw input file bytes
  unchanged; public/central contracts unaffected; external calls **0**; original/
  protected extraction changes=0; model sessions after=0 and no startup inference.
- CPU/RAM check during this small frozen flow: analysis child 3.972s wall /
  6.328 CPU seconds / peak 461.64 MiB; full test flow 9.936s; GUI peak 47.04 MiB;
  maximum measured heartbeat interval 67.71ms. Not a large-file benchmark.
- Native picker return and delete confirmation answers are injected by the
  opt-in automated harness. Actual Tk controls/handlers/DB/matcher/restart are
  exercised. Physical native-dialog clicks and new visual screenshots remain
  unverified; do not interpret automatic PASS as manual visual inspection.

## Packaging and scope

- Final EXE: `dist/notice_crawling/notice_crawling.exe`; distribute the whole folder.
- Distribution: **239,937,312 bytes (239.94 MB)**.
- EXE SHA256: `9477b49d05cebf061571ed6c2ad776025a01f92a20bbbe899f207060f2f4d93a`.
- No DB/SQLite/XLSX/XLS/CSV/private files bundled; no torch/transformers/HF clients.
- No changes to central scraper, Actions, Gemini, Pages or matcher scoring.

New: `preview_selection.py`, `performance_management.py`,
`performance_management_ui.py`, `tests/test_performance_management.py`.
Extended: local `performance.py` existing-only open option, `upload_store.py`
metadata, `upload_ui.py`, dashboard `ui.py`, frozen checker/entry/test runner,
one existing preview test and docs/readmes. No runtime dependency added.

No commit/push. Existing HEAD: `995ab1b51954e83d3536b82a27e76a0d1267665a`.
