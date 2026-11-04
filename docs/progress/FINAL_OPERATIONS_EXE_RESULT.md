# Final operations and Windows EXE verification — 2026-11-04

## Starting point

Started at `d49a7994ddd03817636c963da92560eb14a47a9e`, with a clean working tree
and origin/main divergence 0/0. Reused the implemented preview selection,
performance management, closed taxonomy, user provenance and offline AI code.
No company workbook or production performance database was used or modified.

## Actual GitHub Actions

The newest previous scheduled success, run 41572395988, still used 995ab1b5.
Dispatched run [41746660779](https://github.com/Emoty-9s/notice_crawling/actions/runs/41746660779)
on d49a7994 with bootstrap_state=false; previous central state was restored.

- UTC 2026-11-04 00:25:06–00:39:07; KST 09:25:06–09:39:07 (14m 01s).
- build job 126301274172: success; deploy job 126306997284: success.
- Linux stdlib CI: 588 tests, 61 desktop/model tests explicitly skipped, PASS.
- Actual source collection: all seven SUCCESS. KHIDI 34, KISED 30, RDA 30,
  Seoul R&D 30, KIPA 30, KISTA 60, RIPC 30 observations.
- Pipeline was **PARTIAL**, not complete analysis success: NEW 100, UPDATED 2,
  EXISTING 142, history 244, public feed 0, scraper failures 0, analysis failures
  (including deferred work) 102.
- Production Gemini logs, excluding fake unittest errors: 8 timeouts, 9 HTTP 503,
  then 1 HTTP 429. Calls stopped after 429 as required. These are upstream
  availability/quota failures; no immediate retry loop, key disclosure, model
  substitution, central-state deletion or eligibility relaxation was introduced.
- Published notices.json and metadata.json returned HTTP 200, schema_version=2,
  generated_at=2026-11-04T00:25:42.451428Z, count 0. The independently versioned
  source_status.json returned HTTP 200 with all seven source statuses SUCCESS.
- Root URL returned 404 because publication had only JSON files. Added a static
  allowlisted index page linking the three public endpoints. Its publication
  boundary is covered by the existing Actions staging test; the final code is
  dispatched again after push to verify this fix in actual hosting.

## Fixes and verification support

- Destroying a wrapping Tk label could leave its parent's Configure binding
  targeting the destroyed widget. Added lifecycle cleanup and a real Tk smoke
  regression that checks callback errors during widget destruction and resize.
- The explicit EXE smoke helper pumped events once more after its readiness
  predicate became true, allowing a new refresh to invalidate readiness and
  report a false timeout. Return immediately after observing readiness.
- Expanded the frozen smoke to edit two technical fields and actually change
  work type, check database integrity/foreign keys, and support five-row input
  instead of assuming a six-row fixture and three remaining records.
- Added tests/prepare_final_exe.py and tests/run_final_exe_checks.ps1. These use
  synthetic XLSX and unique DB files under ignored test runtime directories.
- Build preflight now normalizes license-notice whitespace so repeated builds
  pass git diff --check. License wording is unchanged.

## Local tests and fresh build

- Final full unittest: **588 tests, 0 failures, 0 errors, 152.065 seconds, PASS**.
  Earlier baseline/full passes: 139.446 and 147.823 seconds.
- Selection/management focused: 14 PASS; staging focused: 21 PASS.
- Actual Tk dashboard smoke: NIGHT_UI_SMOKE_PASS, including resize cleanup.
- Executed build_windows.ps1, which validates and removes only resolved generated
  output directories before rebuilding. Rebuilt again after the final smoke fixes.
  PyInstaller 6.22.3, Python 3.13.15; fresh build exit 0.
- EXE: `D:\notice_crawling_new\dist\notice_crawling\notice_crawling.exe`
- EXE SHA256: `44761EF43D93F48393A20C4AC0CEB2F62A8729D58B84AA23E6E3F7DA4D95075F`
- Distribute the entire dist/notice_crawling directory, including _internal;
  model binaries are build resources and remain Git-ignored.

## Actual frozen executable scenario

Ran the new EXE twice through its explicit opt-in verification entry point.
Import and restart process exit codes were both 0, frozen=true, status=SUCCESS.

- Five synthetic Excel rows; exact eight-column preview order verified.
- All five selected by default; clear all + save wrote no DB; invert and select
  all worked; Space toggled two individual rows off. Exactly three saved and
  two excluded, with excluded fingerprints absent from DB metadata.
- Management list auto-refreshed to three rows; search by 001245 returned one.
- Edited year, leading-zero management ID, name, client, two allowed technical
  fields (semiconductor and energy storage), and work type (technology transfer).
  All changed fields recorded user provenance.
- Forced offline reanalysis preserved the prior user override. The 21-label
  taxonomy and at most three technical fields were checked; the fixture also
  verified the housing example's three-label display including materials/parts.
- Matcher reflected edits immediately. Delete cancellation preserved the row;
  confirmed deletion removed it and immediately updated matcher results.
- After deletion two rows remained. A second EXE process verified the edited
  record, deleted record's absence, two matcher inputs/results and user override.
- PRAGMA integrity_check=ok, foreign-key violations=0, orphan upload/enrichment
  metadata=0. Source XLSX bytes unchanged; external API/network attempts=0 in
  parent and offline analysis worker. Local model inference occurred in a child
  process; active model sessions after completion=0.
- Dark Night theme, upload/management buttons, GitHub status card and seven
  source cards checked in frozen runtime. Import took 13.414s; restart 0.642s.

Local reports: .run/final-exe-import.json and .run/final-exe-restart.json.

## Frozen live feed check and GUI limit

The same rebuilt EXE synced actual public feed v2 with a temporary cache:
UPDATED then UNCHANGED, GitHub connected, seven source cards, health available,
zero notice cards (matching the published empty feed), and no database created.
Report: .run/final-exe-live-feed.json. This intentional public HTTP check is
separate from the offline upload/AI tests with zero external calls.

Windows computer-use initialization failed twice, including after kernel reset:
`failed to start Node runtime ... (os error 3)`. Therefore native picker clicks
and visual inspection were **not** verified. Frozen tests invoke real Tk button
commands and inject only the picker result and delete confirmation responses;
they do not constitute native coordinate-click verification. The application's
actual delete path still requires its confirmation dialog.

## Remaining operational limitation

Workflow success includes publishable PARTIAL runs. The initial current-policy
run published zero eligible notices because upstream Gemini requests failed.
Do not interpret SUCCESS jobs or zero public count as completed relevance
analysis. Pending central records are preserved for a later run. The final
post-push run ID, Pages root result and provider state are reported in the session.
