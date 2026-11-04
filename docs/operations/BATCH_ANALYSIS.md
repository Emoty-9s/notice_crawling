# Central prefilter, ordinary request batching and durable work

## Scope and evidence

Implemented on top of fa735a4bf6185e91a115ae4984ebddfcc749d021. Collection,
source activation generation, feed v2, local matching/upload/management and the
21-label offline taxonomy retain their existing contracts. The single-notice
GeminiClient.generate and RelevanceAnalyzer APIs remain available.

Ordinary generateContent JSON requests now carry up to five independent public
notices by default, with a hard maximum of ten. This is not Google's asynchronous
Batch API and does not imply its separate pricing or quota allocation.

Official references checked 2026-11-04:

- [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits): RPM, input TPM
  and RPD vary by model/project/tier. Limits apply per project rather than per
  API key. RPD resets at midnight Pacific; active project limits are private to
  AI Studio and cannot be inferred from a public free-tier table.
- [Troubleshooting](https://ai.google.dev/gemini-api/docs/troubleshooting): bounded
  exponential backoff with jitter for transient failures; do not blindly retry
  invalid/authentication requests.
- [Structured output](https://ai.google.dev/gemini-api/docs/structured-output):
  JSON Schema output still requires application-level semantic/identity checks.

Prior runs 41746660779 and 41749301505 confirmed production 503/timeouts/429.
Their previous client discarded detailed quota and retry information, so the
exact historical quota dimension or billing state cannot be reconstructed.
The repository's model variable was read as `gemini-flash-latest`; no secret,
model selection, payment setting or quota was changed. New diagnostics retain
only safe quota metric/ID/limit fields, scope, Retry-After-derived retry time,
and aggregate counts, never raw errors, keys or prompts.

## Prefilter and audit

`config/prefilter_policy.json` controls phrases, contexts and boundary-aware IP/
FTO patterns. Its identifier combines the explicit version and configuration
digest. Every classification stores policy ID, public-input fingerprint, status,
reason code and evaluated_at in Notice.analysis. Title, body or other public
input/config changes trigger reevaluation; a cached classification is stable.

- Related work is CANDIDATE; mixed positive/negative or beneficiary signals are
  REVIEW. Generic analysis/research/strategy words do not establish candidacy.
- Clearly unrelated scope with sufficient readable evidence can skip Gemini.
  Missing/image-only descriptions stay REVIEW unless there is a positive signal.
- Prefilter status alone never authorizes publication. A valid current Gemini
  success remains authoritative, including a previously accepted eligible record.

Downloaded artifact 13284644476 from run 41749301505 into a separate ignored
audit copy. No original state, cache or company database was changed.

| Read-only audit on 2026-11-04 | Count |
| --- | ---: |
| History | 244 |
| Active/unknown deadline | 102 |
| Active CANDIDATE | 19 |
| Active REVIEW | 64 |
| Active CLEARLY_UNRELATED | 19 |
| Current usable success | 0 |
| Legacy successes in full history | 2 |
| AI targets | 83 |
| Previous single requests for active work | 102 |
| Estimated successful normal batches, before retry/budget effects | 17 |

Full-history classification: CANDIDATE 107, REVIEW 118, unrelated 19. Review of
excluded samples found staff group insurance, VDI upgrades, accounting outsourcing,
physical moving services, mentee applications and final-selection result notices.
Mixed IP/training/consulting notices, beneficiary IP support, unclear professional
services and image-body notices remain candidates/review. This is a conservative
rule audit, not a measured false-negative rate or completed Gemini analysis.

Audit source SHA256 before/after:
`a37b33baf47a8c6a65021fdd62ab76157683e373f7af645f4ce774e1dce7c08d`.
Run `python -m tools.prefilter_audit --data-dir <downloaded-copy>` for read-only
counts and public excluded examples. This command makes no API calls or writes.

## Independent decisions and cache

Batch response is `{results:[{notice_id, relevant, category,
participation_type, reason, keywords}]}`. `relevant` retains the existing policy's
meaning; it is not renamed to eligible. The existing schema defines category and
participation_type as nonempty strings rather than closed enums. Any enums in
the configured schema are enforced; arbitrary new enum lists were not invented.

Unknown response IDs are rejected, duplicate requested IDs invalidate that ID,
and each remaining row is independently checked for exact fields/types/schema.
Good rows checkpoint immediately. Missing/invalid rows alone remain RETRY_WAIT;
malformed groups shrink to two and then one, with the old single generate
contract available at the smallest fallback. Every retry/fallback consumes the
same HTTP and token budgets. No unbounded recursion or immediate retry loop.

Only successful results with current policy, content hash and result schema are
reused. A schema fingerprint also invalidates work when the schema changes.
Compatible legacy v2 successes can still be reused. Old successful decisions
are retained on failed reanalysis and archived in previous_results when replaced
by a new success. Stale results cannot enter the public projection.

Public descriptions are length/token bounded, keeping verbatim beginning/end
and qualification/work excerpts. Obvious email/phone/contact-name fields are
redacted from provider payloads. The central path never reads company Excel,
local performance SQLite, matcher results or offline-AI private data.

## Durable state and scheduling

Notice.analysis holds content/policy/schema target, PENDING/IN_PROGRESS/
RETRY_WAIT/SUCCESS/PERMANENT_FAILURE/STALE_POLICY, attempts, last attempt, next
retry, last error, fallback cap and lease. History, queue and decisions share
one atomic notices.json replacement; there is no separate queue file to drift.
Legacy records without analysis metadata load without rewriting at read time.
Corrupt/incomplete present work state is rejected, not silently reset.

The pipeline saves complete collected history before prefilter/analysis, claims
work before provider calls, and checkpoints each good/failed result. A failed
claim/save aborts further API work. Windows native sharing-lock replacement
failures receive five short bounded attempts, preserving the prior full file.

An OS-held writer lock prevents overlapping local pipeline writers. Actions
retains concurrency group central-notice-pages with cancel-in-progress=false.
Claims lease for 900 seconds; live leases are not resubmitted, expired leases
become due again. Content/policy changes invalidate old work targets safely.

Priority is imminent NEW CANDIDATE, other NEW CANDIDATE, UPDATED CANDIDATE,
due CANDIDATE, then REVIEW/backlog. NEW/UPDATED order also applies within REVIEW.
REVIEW aged at least seven days receives every fourth slot; alternate calendar
days give an aged REVIEW the first slot so tiny budgets cannot starve it forever.
Expired notices are stored but never submitted.

429 stops all further HTTP calls in that run, sets retry times for outstanding
work, and carries a global cooldown into the next run, including new arrivals.
Retry-After and RetryInfo are lower bounds. Minute limits wait at least 60s,
unknown limits conservatively wait an hour; daily/zero limits wait for Pacific
midnight (08:00 UTC conservative fallback if IANA timezone data is unavailable).
No keys are rotated to bypass quota. A reported limit of zero requires operator
review; batching cannot create quota or fix billing.

503, timeout/network and retryable 5xx have at most two retries by default with
2s/4s exponential delay and jitter, in addition to the real-provider 6s start
interval. A delay greater than 30s is deferred rather than slept through. Three
consecutive transport failures open the circuit. Authentication/invalid request/
model failures stop the run for operator action and mark affected work permanent;
fixing the cause also requires explicitly requeuing that permanent work. Failed
or malformed output is never converted into an ineligible decision.

## Budgets and workflow

All settings use the `ANALYSIS_` prefix. Defaults:

| Suffix | Default | Meaning |
| --- | ---: | --- |
| BATCH_SIZE | 5 | Ordinary request group, maximum 10 |
| MAX_API_REQUESTS_PER_RUN | 12 | Request attempts including retries/fallback |
| MAX_NOTICES_PER_RUN | 60 | Unique notices; retries do not add new unique notices |
| MAX_INPUT_TOKENS_PER_RUN | 120000 | Conservative UTF-8-byte input bound including policy/schema overhead |
| MAX_RUN_SECONDS | 600 | Analysis session budget, with request timeout headroom |
| MIN_REQUEST_INTERVAL | 6 | Real-provider minimum remains at least 6 seconds |
| MAX_RETRIES | 2 | At most 4 accepted; every retry spends request budget |
| CIRCUIT_THRESHOLD | 3 | Consecutive transport failures |
| LEASE_SECONDS | 900 | In-flight claim recovery |
| MAX_BATCH_INPUT_TOKENS | 18000 | Conservative per-group bound; smaller bodies/groups as needed |
| MAX_BODY_CHARS | 12000 | Maximum body excerpt size before byte-budget adjustment |

The legacy run_pipeline analysis_max_calls argument is retained as an alias for
HTTP request budget. Metrics distinguish submitted notices including retries,
unique submitted notices, accepted successes, failed/deferred notices, retries,
provider-reported input/output tokens, estimated input bound and elapsed time.

Workflow exposes selected repository variables and a manual request-cap choice
of 1/3/6/12; manual default is 3 for controlled validation, scheduled default is
12. Cron remains `17 22 * * *`: nominal **07:17 KST daily**, with normal GitHub
scheduling delays possible. No extra analysis cron was added without real
quota/cost evidence.

Previous state restore/validation still precedes requests. After analysis or a
failed analysis step, an always-running checkpoint validator gates an always
state-artifact upload. State retention remains the existing 90 days; daily runs
refresh it. An expired/missing artifact refuses silent reset. Checkpoints and
leases survive ordinary process failures when the artifact upload can execute.
Analysis budgets leave substantial headroom under the 45-minute workflow limit.

An abrupt runner/VM loss before artifact upload can still lose changes since
the last remote artifact. Also, the provider offers no idempotency guarantee for
a response received immediately before process loss; expired-lease retries are
at least once in that narrow window. Local atomic checkpoints, OS/workflow
serialization, valid-state upload on failure and bounded run times reduce these
windows; they do not falsely promise distributed exactly-once billing or an
artifact backup surviving more than 90 days of total workflow inactivity.

## Publication and diagnostics

Every completed run publishes current eligible successes immediately, regardless
of remaining backlog. notices.json/metadata.json remain v2 with exactly their
prior fields. Unknown deadlines retain the conservative existing policy.

Operator diagnostics separately report COLLECTION, PREFILTER, ANALYSIS,
PUBLICATION; active/history counts, three prefilter states, durable work-state
counts, eligible count, zero-public reason, cache hits, error counts, next retry,
stop reason and model/quota metadata. A run with not-yet-due work remains PARTIAL
even if it makes no API calls. CHECKPOINT metrics are marked incomplete; FINAL
metrics follow successful public output. Detailed operator metrics never go
into Pages or public metadata.

## Validation

Live evidence: scheduled run 41760195408 completed build/deploy SUCCESS. All
seven sources succeeded; history 244, active 102, prefilter 19/64/19. Two HTTP
attempts for five distinct notices (one timeout, then 429) confirmed the response
quota GenerateRequestsPerDayPerProjectPerModel-FreeTier, limit 20. All 83 targets
were persisted RETRY_WAIT until 2026-11-04T08:00:00Z; public 0 means incomplete
analysis, not a completed determination that no notices qualify.

Latest core run 41760245154 at fb5ccf1 completed build/deploy SUCCESS, Ubuntu
635 tests PASS (64.824 seconds, optional desktop tests skipped). It restored
artifact 13291190071, made zero provider calls and retained all 83 retry records.
Pages root/feed/metadata HTTP 200, feed/metadata schema v2. The frozen EXE synced
the deployed feed UPDATED then UNCHANGED, seven source cards, no company DB.

Observed artifact 13290932133 was created later than 13291190071 despite its
lower ID. Restore selection now orders by created_at before the ID tie-breaker.
The actual GitHub-script body passed two local Node mock-response cases with
reversed IDs/input order and a newer non-main artifact; Actions focused suite
21 PASS. No additional manual dispatch was made for this selection-only follow-up.

Final local regression: 635 unittest tests PASS, failures 0, errors 0,
223.065 seconds with ANALYSIS_MAX_API_REQUESTS_PER_RUN=3, matching the manual
workflow environment. Projection/feed/local-sync smoke and frozen EXE synthetic
import/management/restart checks PASS; no company data or provider calls used.

The first capped verification run 41759157113 stopped before collection: the
manual three-request limit leaked into legacy fixture expectations. Fixture
defaults are now isolated, with a separate regression proving that operational
environment budgets really defer remaining history. No provider requests or
state uploads occurred in that failed run. Queue parsing also passes the actual
output_schema to the validator so configured enums are enforced end to end.

The dedicated no-provider suite covers related/unrelated/mixed/insufficient-body
prefiltering, IP boundaries, version/hash changes, five/ten groups, missing/
duplicate/unknown/invalid rows, malformed fallback, cache/schema changes,
429 Retry-After/date/quota, 503 retry/circuit, timeout resume, budgets,
checkpoint write failure, KeyboardInterrupt/lease recovery, OS writer collision,
legacy load, input bounding/redaction and progressive feed v2 sync.

Fresh Windows EXE build and synthetic selection/management/offline-AI import and
restart tests passed. Five rows → deselect two → save three → edit two technical
fields/work type → delete one → restart with two records; orphan metadata,
foreign-key violations and external inference/network attempts all zero.
EXE SHA256: `E171BA1B86E03ECA28BFE6CFEBB95766AB2358F3E0A30DF37252C8745FBB34E7`.
The final full unittest count/duration, commit and one capped live run are
reported with their actual evidence in the session. Native coordinate/picker
clicks remain distinct from the explicit frozen Tk-command verification.
