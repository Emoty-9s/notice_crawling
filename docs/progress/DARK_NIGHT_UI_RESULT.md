# Dark Night 업무 모니터링 대시보드 — 2026-11-02

## Implemented UI

- Charcoal/navy-black vertical background gradient, dark cards, off-white text,
  muted secondary text and four dim orange bands beneath status cards.
  No orange filled buttons or neon animation. Selection uses a thin muted accent.
- Top GitHub card: CHECKING/FALLBACK yellow, verified feed blue, no usable cache
  red. Text accompanies every dot. A single Tk after loop updates brightness
  continuously with a four-second period (two-second rise/fall); lights never
  switch fully off. There are no Tk-thread network requests or sleeps.
- Seven named institution cards display the last CENTRAL result, not local
  availability probes. SUCCESS green / ERROR red / unavailable UNKNOWN gray.
  Cached health is labeled stored status and its attempt time remains visible.
- Main content: public notice cards, institution/title/application period/category/
  participation type, search and NEW/UPDATED/SAVED markers. Markers compare with
  the cache loaded at session start; they do not modify central Notice status.
  New and updated cards sort first. DB/cache paths are in Settings, not the main UI.
- Per-notice matching accordion, collapsed initially. Rank, project name, total
  points, component reasons/terms and score sum use the existing matcher output.
  Match year remains explicit; TOP N changes invalidate previous results.
- Internal detail page with back navigation, public summary/category/participation/
  keywords/relevance reason, original-link button and the same matching results.
  Only the explicit original-link button opens the default browser. No arbitrary
  script/file/credential-bearing URLs are launched.
- Removed the recommendation selection tree, separate reason panel and the old
  four-pane layout. There is no duplicate recommendation view.

## Data, security and asynchronous behavior

`monitor.py` consumes existing FeedClient, cache validation, read-only DB loader
and matcher presenter. Missing/corrupt DB does not prevent notice display.
No DB is initialized, written or uploaded. Client/attorney/notes fields are not
included in rendered match explanations. Cache/DB path collisions fail before
network or writes. Cache filenames explicitly supplied by the user are retained.

A daemon worker loads the local cache and performs feed sync. A queue transfers
results to Tk, polled with after(). The UI paints before work starts. Repeated
sync clicks cannot create overlapping workers; settings cannot change during a
sync. Generation checks ignore stale results, and shutdown cancels animation/
poll callbacks without waiting for network timeout or making worker Tk calls.
Last-good same-origin feed cache remains usable when requests fail. Without
valid cache, the main list shows an explicit error. `--offline` disables startup
requests. `--base-url`, `--cache`, `--db`, year and TOP N remain explicit options.

The existing public notices.json/metadata.json schema and feed eligibility rules
are unchanged. A separate optional `source_status.json` is produced during the
existing validated Pages staging step. Exactly seven allowlisted source rows
contain only `source_id`, `status`, `checked_at`, `notices_found`. The envelope
contains schema_version/generated_at. No private state file, error_message,
error_type, notice bodies or credentials are copied to Pages. Disabled/missing
attempts are UNKNOWN. Historical valid numeric count/date are the only metadata.
The optional local health sidecar is schema-validated, source-bound and marked
cached on fallback. A 404/invalid health response never breaks valid feed sync.

Workflow structure, permissions, artifact restore policy and pipeline are
unchanged; only the staging step's display name reflects the explicit public
health allowlist extension. Repository sites remain enabled=false. No scraper,
Gemini, matcher, performance model/schema or public feed projection was modified.

## Verification

- Full unittest: **472 tests / OK / 44.448 seconds / exit 0**, original 459 retained.
  Twelve monitor tests cover online/unchanged/fallback/no-cache, DB independence,
  path safety, origin binding, health whitelist, unknown states, ordering and URL
  safety. One integrated Actions test verifies private errors/unknown sources
  cannot enter the health artifact. Existing staging test now expects the
  explicitly allowed health document alongside the unchanged feed pair.
- `python tests/ui_dashboard_smoke.py`: **NIGHT_UI_SMOKE_PASS**. Real Tk tests
  accordion open/close, original 22-point matcher result, explicit year/TOP N,
  component evidence, detail/back, browser dispatch, all connection colors,
  source SUCCESS/ERROR colors, no private field rendering, immutable synthetic
  DB/cache, a blocked worker with a live Tk heartbeat, and callback shutdown.
- `build_windows.ps1`: final PyInstaller 6.22.3 / Python 3.13.15 build exit 0.
  Test-Path of the requested executable is True. No new hidden imports/data files
  were needed. Distribution inspection found no private DB/cache/xlsb/env/keys.
- Final exe live smoke (`--smoke-report ... --feed-url` and a synthetic
  `--smoke-db`): exit **0**, frozen=true, **UPDATED -> UNCHANGED**, GitHub text
  **GitHub 연결 정상**, **7 source cards**, **1 public notice**, accordion=true,
  **2 matching results**, detail=true, back=true, removed-selection=true,
  Tcl/Tk **8.6.15**, cache path correct, no new database created.
- Computer Use directly inspected the actual exe at maximized and normal window
  sizes: dark theme, header, source cards, public notice, expanded matches,
  internal detail and actual back navigation. Clicking original opened the
  default Edge browser on the RIPC PMS notice. No import/crash dialog appeared.
  The process ended normally after closing its window.

The real public health endpoint was not yet deployed during the initial exe
screen verification, so all seven cards correctly remained gray rather than
inventing SUCCESS. Live publication verification is recorded below when available.
No production/private DB was used for validation; synthetic files and smoke
reports remain under ignored `.run/`. Screens used public feed content.

## Executable and remaining limits

`D:\notice_crawling_new\dist\notice_crawling\notice_crawling.exe`

Final executable SHA-256:
`EA8ED1C279C0D07C7B642707F68653F3C99627A10B32F1CF338836BB22EEF567`.

Distribute its whole directory including `_internal` and README.txt. Default
user data paths remain under `%LOCALAPPDATA%\NoticeCrawling`, outside the bundle.
Build artifacts are ignored and uncommitted. Other-machine/SmartScreen/signing
behavior was not tested. Very large feeds are rendered as Tk cards without
virtualization. Explicit year and an existing valid local DB are required for
matching. Settings paths apply to the current session; persist them via startup
arguments/a shortcut or use the standard default data locations.
