# M16.1 — Windows executable packaging

## Status and correction

**PASS — independently rebuilt and executed on 2026-11-02.**

The previous document declared PASS based on a user-reported external build.
That was not independent verification of this workspace's executable. This
report replaces that evidence with the actual build and execution below.
An executable already existed at inspection, but existence alone was not used
as proof: `build_windows.ps1` rebuilt the distribution from the current entry.

## Actual build

- Project Python: `.venv/Scripts/python.exe`, Python 3.13.15, Windows 11 x64.
- `pip install --disable-pip-version-check --retries 0 -r requirements-build.txt`
  confirmed PyInstaller 6.22.3 and its dependencies installed in `.venv`.
- `build_windows.ps1`: exit 0, PyInstaller COLLECT completed. Final rebuild
  includes the explicit packaged smoke mode.
- `Test-Path D:\notice_crawling_new\dist\notice_crawling\notice_crawling.exe`:
  **True**.
- Executable SHA-256:
  `72325C90FAA5FC9D8603C8D946D1595FE707E3EA1C907B94C19A04AAE73F2670`.
- Distribution: `dist/notice_crawling/notice_crawling.exe`, `_internal/`,
  `README.txt`. The whole folder must be distributed together.

The existing build configuration needed no hidden imports or data-file fixes.
PyInstaller collected Tk/Tcl, SQLite and Python runtime hooks. Warning-file
entries for platform-specific/conditional modules were reviewed; actual import
and runtime checks below passed. Build/spec/cache outputs remain ignored.

## Actual execution

The final executable ran in smoke mode with:

```powershell
$p = Start-Process -FilePath '.\dist\notice_crawling\notice_crawling.exe' -ArgumentList '--smoke-report D:\notice_crawling_new\.run\windows-smoke.json --feed-url https://emoty-9s.github.io/notice_crawling/' -WindowStyle Hidden -Wait -PassThru
$p.ExitCode
```

Observed exit **0**, report status **SUCCESS**, `frozen=true`:

- Public Pages feed synchronization: **UPDATED**, then **UNCHANGED** using
  the actual bundled FeedClient and network/JSON/cache modules.
- Real Tk dashboard constructed, updated and destroyed; Tcl/Tk **8.6.15**.
- Title: `공고 · 로컬 실적 매칭`; explicitly supplied cache path retained.
- An isolated temporary cache was used and removed. No personal DB used;
  nonexistent test DB was not created.
- Default arguments point to `%LOCALAPPDATA%\NoticeCrawling\cache\snapshot.json`
  and `%LOCALAPPDATA%\NoticeCrawling\performance.db`, outside installation and
  `_internal`. Existing explicit `--cache`/`--db` overrides remain supported.

Normal executable launch was also observed with Computer Use: the full Korean
dashboard rendered, default user paths were visible, and no import-error or
crash dialog appeared. With no default cache, the UI correctly displayed
`INVALID_OR_MISSING_CACHE`. Closing the window ended the process.

Normal launch remains the offline read-only UI. Feed synchronization above is
an explicit diagnostic mode (`--smoke-report` plus `--feed-url`), not an added
automatic download or UI sync button. A full interactive match using a personal
DB was not performed. Other-PC compatibility and signed-installer/SmartScreen
behavior are outside this local runtime verification.

## Environment and distribution checks

Inside the sandbox the script was blocked by AuthorizationManager and the
network smoke failed with SyncError. Approved normal PowerShell execution
built successfully and the identical exe smoke passed. No execution policy,
Defender, SmartScreen or other security settings were changed.

Distribution inspection found no DB/SQLite files, private xlsb, `.env`, keys,
central state snapshots, personal cache or sites.yaml. Source/config/test trees
are not copied as add-data. `dist/` and `build/` remain ignored and uncommitted.
Only reproducible code/configuration, tests and documentation are committed.

## Tests

Packaging tests: **6 PASS**, including the original four frozen/default/explicit
path tests plus normal offline entry and explicit diagnostic routing.
Final full unittest result is recorded in CENTRAL_REPAIR_RESULT.md.
