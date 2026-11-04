# Local performance upload — 2026-11-03

## Scope and implementation

Only the local performance upload flow was added. Dashboard colors/layout,
GitHub/source status cards and sync presentation were preserved. Earlier
retention/seen changes were already present and remain uncommitted separately.
No central scraper, Actions, Gemini analysis, Pages deployment, public notice
contract, central state contract or matcher scoring code was changed for upload.

- Toolbar `실적 업로드` opens the native file chooser. Supported extensions are
  XLSX (openpyxl 3.1.5 + defusedxml 0.7.1), XLS (xlrd 2.0.2) and CSV (stdlib).
  Desktop requirements are separate from central runtime requirements.
- Every nonempty sheet is explored. Header candidates in the first 60 rows use
  alias matches and following row density. Unknown but plausible headers remain
  explicitly reviewable. Empty rows/sheets, title/preamble rows, repeated header
  rows and total/subtotal rows are excluded from performance candidates.
- Editable ALIASES dictionary covers management IDs, project/client/description,
  dates/year/period, technical field/work type/amount and explicit keywords.
  NFKC/case/space/underscore normalization and trailing parenthetical descriptions
  are handled without substring matching unrelated field names.
- Conservative column heuristics recognize years, date candidates, currency
  amounts, prefixed/zero-padded IDs, long descriptions and institution patterns.
  Inferred/ambiguous fields and unclassified columns are marked `확인 필요`.
  Ambiguous numeric IDs/currency values are not arbitrarily assigned.
- Management IDs are string/None, with literal leading zeros, slashes/prefixes
  and zero-padded integer Excel display formats preserved. Missing IDs are valid.
- All source columns survive in raw_source, including duplicate/blank headers
  represented by distinct stable labels. XLSX formulas and number formats are
  preserved. Formulas/macros/external links are never executed. Formula caches
  may be read; missing XLSX cached values are flagged for review.
- searchable_text contains valid original cell text. A separate adapter text
  includes unmapped business prose for the existing matcher's description rule
  while excluding mapped identifiers, amounts, years and dates. No new scoring
  rules, weights, embeddings or AI classifications were introduced.
- Preview displays filename, populated sheet count, candidates/normal/review/
  excluded counts, sheet/row, management ID, project/client/year/technology/status,
  mapping rationale and the complete original row. The table displays up to
  1,000 rows; save processes all preview candidates. No DB writes on selection.

## Local persistence and duplicates

The configured existing performance DB is reused. Save explicitly initializes a
missing Performance DB only after user confirmation. Existing `performances`
columns, Performance dataclass, database application ID and user_version=1 are
unchanged. The additive `performance_uploads_v1` table stores management/date/
amount/raw/searchable/fingerprint/source-location/review/mapping/normalized data.
Foreign keys remove companion metadata when the existing DAO deletes a record.

The importer checks exact normalized row fingerprint, project+client+known year,
and management ID with project+client+year context. ID alone never merges records.
Duplicates retain the existing record and are counted. Row savepoints isolate
validation/constraint failures; fatal database errors roll back the transaction.
Source data/SQL exceptions are not printed or included in user-facing messages.

Save reloads the DB on a background worker and clears cached match results.
The current list/detail/expanded accordion refreshes without restarting. A pending
feed worker cannot permanently overwrite fresh import results: reload repeats
after that sync completes. Existing explicit reference-year/TOP N rules remain.

Empty DBs show `등록된 실적이 없습니다. 실적 업로드를 통해 데이터를 추가하세요.`
No fixture/demo company data is initialized during normal production launches.

## Privacy and validation

- Workbook reads and DB saves are local. Source files are never copied/modified.
  Only filename/count/error-type diagnostics are appropriate; no cell-content
  logging was added. Source filename is stored locally, without the full path.
- There is no Gemini/OpenAI/HTTP/analytics/upload call in the import service.
  Tests block urllib/socket/feed-sync/Gemini calls during ingestion and UI flow.
- Full unittest: **520 tests / OK / 47.930 seconds**, including **30 new upload
  cases and 1 packaging case**, in addition to the prior 489 tests. Actual XLS
  fixtures are generated locally with test-only xlwt 1.3.0. All readers were
  installed and these cases were run, not skipped, in this verification.
- `tests/ui_upload_smoke.py`: **UPLOAD_UI_SMOKE_PASS**, real Tk widgets, real XLSX,
  file-picker dispatch, read/preview, no early DB initialization, save, immediate
  positive matching, restart persistence and untouched input bytes.
- Existing `tests/ui_dashboard_smoke.py`: **NIGHT_UI_SMOKE_PASS**.
- PyInstaller rebuild: **exit 0**, Python 3.13.15 / PyInstaller 6.22.3. Reader
  libraries are included; no new user setup is needed for the distribution.
- Actual frozen EXE import: **exit 0 / SUCCESS**, two populated sheets/two preview
  rows, leading zero preserved, preview did not write DB, saved=2, records_after=2,
  matching_count=2, positive_match=true, source_unchanged=true, external_calls=0.
- A **separate EXE process** with `--verify-only`: **exit 0 / SUCCESS**,
  records_before=2, records_after=2, matching_count=2, external_calls=0.
- The opt-in `--upload-smoke-report` mode accepts caller-supplied files only.
  It contains no fixture/demo generator and is never entered on normal launch.
  Its native file-picker return is injected to make runtime checks repeatable;
  actual file-picker clicks/screenshots were **not** verified. Both native
  Computer Use entry points failed with a missing native pipe. This is a specific
  remaining manual UI validation, not evidence that the upload function failed.

EXE: `D:\notice_crawling_new\dist\notice_crawling\notice_crawling.exe`

SHA-256: `1DBD9C236F1299DE09273B65F2F115EDB0EB94095C68490A91D441EBB701F630`

Ignored count-only reports: `.run/upload-exe-import.json`, `.run/upload-exe-restart.json`.
Generated synthetic workbook/cache/DB inputs stay under ignored
`tests/fixtures/performance_upload/runtime/`. Production data was not used.

## Changed files for this upload task

- `src/local_client/upload.py`, `upload_store.py`, `upload_ui.py` (new).
- `src/local_client/ui.py` (button/dialog/reload/empty-state integration),
  `performance.py` (foreign key enforcement only).
- `requirements-desktop.txt`, `requirements-test-desktop.txt` (new),
  `requirements-build.txt` (include the desktop runtime readers).
- `tools/windows_entry.py`, `tools/windows_upload_smoke.py` (new opt-in upload
  verification), `tools/windows_README.txt`.
- `tests/test_upload.py`, `tests/ui_upload_smoke.py`, `tests/prepare_upload_exe.py`
  (new), `tests/test_windows_packaging.py`.
- `.gitignore` (generated tests-only runtime inputs), `README.md`,
  `docs/progress/CURRENT_STATE.md`, this report.

No new commit or push was made. Existing HEAD is
`995ab1b51954e83d3536b82a27e76a0d1267665a`; the prior retention work was already
uncommitted when this task began and has not been discarded or packaged as a
separate commit.

## Limits

- No manual mapping editor in this iteration. Review-required rows can still be
  saved, with original data preserved for later refinement.
- Encrypted workbooks are unsupported. XLS exposes cached formula values rather
  than original formula expressions. Excel-lost leading zeros without text or
  an explicit zero-padding display format cannot be recovered reliably.
- 50MB file / 150MB uncompressed XLSX / 50,000 rows per sheet / 256 columns /
  500,000 cells per workbook. Exceeding limits reports an error without importing
  an arbitrarily truncated file.
- Central workflows intentionally keep their stdlib setup. Desktop tests skip
  when desktop reader dependencies are absent; install the desktop test
  requirements to run the full upload coverage locally.
