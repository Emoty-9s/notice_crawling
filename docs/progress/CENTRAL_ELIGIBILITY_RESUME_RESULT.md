# Central eligibility resume — 2026-11-04

## Resume point

- User handoff: 585 tests / 8 failures, followed by 18 passing focused M16 tests.
- Preserved the existing working tree, including upload, local AI, taxonomy and management work.
- First resumed full run: 585 tests, 1 failure, 0 errors, 174.539 seconds.
- Remaining failure: `test_real_details_pipeline_with_derived_ripc_json_and_kista_subset`
  expected 2 public notices on April 3, although the RIPC fixture closed April 2.
  Actual count 1 followed the active-only contract. Moved this integration clock
  to the last open day; retained independent expired-history/no-call tests.

## Final verification

- Full unittest: **588 tests, 0 failures, 0 errors, 144.260 seconds, PASS**.
- Eligibility/pagination focused: 12 PASS.
- History/NEW focused: 6 PASS; feed: 18 PASS; local sync: 24 PASS; monitor: 12 PASS.
- Gemini: 31 PASS; Actions publication validation: 21 PASS.
- `tests/ui_dashboard_smoke.py`: NIGHT_UI_SMOKE_PASS. Verified actual Tk cards,
  matching/detail/back, acknowledgements persisted independently of central NEW,
  restart, heartbeat, shutdown and cache/DB bytes unchanged. Source card counts
  match the eligible collection even when raw health counts are 999.
- `python -m tools.eligibility_projection_smoke`: PASS. Temporary synthetic state
  and feed output only; history 6, public eligible 4, schema v2 in both JSON files.
  First run: 3 fake analysis calls; second run: 0. NEW changes true to false.
  Current cached success is reused; old/missing policies are reanalyzed; expired
  and nonparticipating records remain in history and stay out of the feed.
  Local sync/dashboard and Actions staging pass for both central runs.
- `git diff --check`: PASS; Windows LF/CRLF notices are warnings only.

## Policy and implementation

- Storage preserves complete current observation records, including old deadlines;
  no deadline+90 deletion is called by the central pipeline or local projection.
- Current analysis requires SUCCESS, current policy identifier, matching content
  hash and complete decision fields. Participation follows the version 2 policy:
  patent-firm provider/partner/bidder roles, excluding beneficiary-only notices.
- Unknown deadlines remain eligible unless an explicit closure statement exists.
  Known deadlines are active through their Korean calendar date.
- Queue order: NEW, UPDATED, active unanalyzed, remaining enabled-source backlog.
  Closed notices are filtered before analysis. Default budget 60 calls; actual
  GeminiClient requests start at least 6 seconds apart; 429 pauses that run.
  Throttle regression uses injected monotonic time/sleep, with starts 0/6/12.
  Ordinary fake clients do not sleep.
- Public/local schema v2; is_new is a strict bool and remains independent of seen.
  Publication validation also rejects integer values masquerading as bools.
- Updated README, Windows instructions and obsolete docstrings; marked the old
  retention/seen report as historical rather than deleting prior work.

## Official pagination smoke

`python -m tools.eligible_collection_smoke` fetched/parsed listing pages only.
No real AI calls, central state/cache writes, or private DB/Excel access.

| Source | Result | Pages | Unique notices | Method |
| --- | --- | ---: | ---: | --- |
| khidi_business | PASS | 3 | 34 | GET |
| kised_bid_public | PASS | 3 | 30 | GET |
| rda_bid | PASS | 3 | 30 | GET |
| seoul_rnd_notice | PASS | 3 | 30 | GET |
| kipa_bid | PASS | 3 | 30 | GET |
| kista_ippro | PASS | 3 | 60 | GET + existing POST pager |
| ripc_pms | PASS | 3 | 30 | GET + existing POST/AJAX |

Maximum collection pages remains 3. Request totals can include robots/bootstrap
requests in addition to listing pages. Checked-in `config/sites.yaml` and the
Actions operational-config generation were unchanged. Live counts are listing
observations, not Gemini eligibility counts. Live detail scraping and real AI
analysis were deliberately outside this scraping-only smoke.

## Commit scope

The inherited UI, packaging and documentation combine central projection with
upload/local-AI/management dependencies. Commit the verified coherent tree
together instead of leaving committed UI imports pointing to untracked modules.
Preserve all inherited source, tests, synthetic fixtures and license notices.
Ignored model/tokenizer binaries, local runtime reports and company data are not
included. This resume does not rebuild or claim a new frozen Windows executable.

Fetched origin successfully; local HEAD and origin/main had divergence 0/0 before
the commit. Final commit SHA and push status are reported in the session output.
