# Retention and local seen state — 2026-11-03

> Historical verification of the previous policy. Superseded on 2026-11-04:
> central observation history is preserved without deadline retention deletion;
> public/local views project active eligible notices; central `is_new` is independent
> of user acknowledgements. See CURRENT_STATE.md for the current contract.

## Implemented policy

- Use Korea calendar dates. Keep active notices and notices with unknown,
  invalid or ongoing/textual deadlines. Never infer expiry from creation date.
- Keep a known deadline through day +90 inclusive. Starting day +91, remove
  the complete notice record from the current central state/public feed/local
  cache snapshot without creating an archive or tombstone.
- Central pipeline validates restored state as before, compares collected
  corrections, removes expired rows before analysis/merge/save, and prevents
  expired scraped rows from re-entering state or spending Gemini call budget.
  A corrected/extended deadline can keep the same identity and cached analysis.
  Disabled/failed/unobserved sources do not exempt expired notices from deletion.
- Public projection independently enforces the same deadline rule using its
  explicit generation timestamp. Existing public eligibility/security allowlists
  and schema v1 remain unchanged.
- Local cache validates the complete incoming pair before retention, atomically
  rewrites the retained pair and adjusts notice_count without changing generation
  time. The same rule runs on cache loads, offline/fallback and online reception.
  While the UI is open, a serialized background worker checks once per minute.
  No network request is required for periodic retention. Unchanged rows are not
  rerendered, avoiding scroll/accordion disruption.

## User acknowledgement

- Unseen notice IDs are NEW regardless of age, sync or app restarts.
  Loading old cache does not implicitly acknowledge any notices.
- Opening detail or clicking the row's `확인 처리` persists the notice ID and
  acknowledged updated_at in `<cache filename>.<profile hash>.seen.json`. The default EXE cache
  and sidecar reside under the Windows user's LOCALAPPDATA directory.
- Feed origins are namespaced. The cache and sidecar are separate; cache refresh
  does not erase acknowledgements. Other users' default data directories remain
  independent. A hash of the local profile path also separates acknowledgements
  when users explicitly share a custom cache directory; no username is stored.
- Seen notices are SAVED; a later changed version is UPDATED, never NEW again.
  Detail refreshes caused by sync/filter/matcher settings do not acknowledge
  a version the user did not explicitly open.
- Invalid/unwritable seen state is reported in the status bar and is not
  silently overwritten. Failed writes do not falsely acknowledge a notice.
- No seen data is added to public feed, central state, Gemini inputs, matcher
  inputs or performance DB. Existing Notice/DB schemas and scoring are unchanged.

## Validation

- Full unittest: **489 tests, OK, 45.918 seconds** (472 existing +17 new).
  Historical integration fixtures now run with explicit clocks inside their
  retention windows; actual captured HTML and matcher assertions are preserved.
- Additional final monitor regression: **12 tests, OK**.
- Real Tk interaction smoke: **NIGHT_UI_SMOKE_PASS**, including initial NEW,
  detail acknowledgement, explicit acknowledgement, persisted state after
  restart, remaining unseen notices, matcher, detail/back, browser dispatch,
  asynchronous sync heartbeat and shutdown.
- Final PyInstaller build: **exit 0**, Python 3.13.15 / PyInstaller 6.22.3.
- Rebuilt EXE actual public GitHub sync: **exit 0, SUCCESS**, UPDATED/UNCHANGED,
  `GitHub 연결 정상`, seven source cards and available public source status.
  Zero retained notices is expected: the currently published notice's deadline
  is 2026-07-20, which is beyond 90 days on 2026-11-03.
- Rebuilt EXE isolated loopback feed: **exit 0, SUCCESS**. Three producer rows
  (two retained + one expired) become two notice cards. Accordion, two matching
  results, detail/back and `seen_persisted=true` are verified in the frozen app.
  Server and isolated app processes were closed; no production DB was used.
- `git diff --check`: pass. Screen-capture tooling remains unavailable in this
  session; these are real Tk/frozen-runtime interaction tests, not a new visual
  screenshot inspection.

EXE: `D:\notice_crawling_new\dist\notice_crawling\notice_crawling.exe`

SHA-256: `2CF7A125C58D1D94F2D5A319EAD293A86CB32CBF1DB71A5A97993B0FC95F7962`

Ignored local reports: `.run/retention-live-smoke.json`,
`.run/retention-fixture-smoke.json`.

## Deployment boundary

Code and rebuilt distribution are local and uncommitted. No push, paid Gemini
run or production Actions dispatch was performed. Central deletion takes effect
after this code is deployed and the next central pipeline runs; local deletion
already applies when using the rebuilt EXE. The existing GitHub state artifact
selection/restore/retention contract was not changed. Existing historical Actions
artifacts are not purged by this change; no new notice archive is created.
