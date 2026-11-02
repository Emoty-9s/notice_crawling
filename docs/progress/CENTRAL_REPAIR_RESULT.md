# Central scraper / Gemini progression repair — 2026-11-02

## Evidence and scraper fix

Baseline commit: 0186080. Working tree initially clean. Actions run
41405916425, build job 125147779340 reported both sources failing at
`parse_detail` with `StructureError`; pipeline PARTIAL, not a fatal workflow.

Local network initially failed DNS inside the sandbox. An approved external
network probe reproduced `empty detail title/body` for both adapters. KHIDI's
first pinned notice (linkId 48952024) contains only an external poster image;
Seoul's second notice (seqNo 1130) contains an inline base64 image. Text cleanup
correctly drops images, but the source lifecycle aborted all records on an
empty extracted body. List selectors, identity checks and text detail parsing
were working. No TLS/UA/encoding/redirect/pagination or anti-bot workaround was
needed. The adapters intentionally fetch the current first list page; KHIDI
includes pinned rows (14), Seoul has 10. Historical pagination is unchanged.

Only these two adapters opt into an image-only body representation. It clearly
states text was not extracted and OCR was not performed. External HTTP(S)
image URLs or inline image SHA-256 identifiers preserve resource identity;
base64 payloads are not copied into analysis/state. Empty/invalid bodies still
fail, and title/identity checks and source-level partial semantics remain.
This is collection of the observed poster reference, not extraction of its
eligibility conditions. No OCR, attachment download, or image API calls added.
An unchanged external image URL cannot detect changed pixels behind that URL.

Live verification: `python -m tools.central_scraper_smoke --all-details`
returned KHIDI SUCCESS (14 list / 14 parsed and normalized details) and Seoul
SUCCESS (10 / 10), exit 0. Optional response captures remain in ignored `.run/`.
The probe never writes central state or the public feed and never calls Gemini.
Regression coverage includes external/inline images, hash changes, normal text,
missing/invalid images and existing empty-body/identity checks.

## Gemini investigation

The same Actions run logged 89 analysis failures: API_ERROR and
NETWORK_OR_TIMEOUT. Summary: NEW=90, EXISTING=30, stored=120, feed=1;
persisted totals SUCCESS=2, PENDING=118, FAILED=0. Thus 89 new attempts failed
retryably, one newly analyzed record succeeded; 29 prior PENDING records were
retained and one prior SUCCESS reused. There was no analysis cap, batching,
rate-limit pause, or retry loop. `API_ERROR` is deliberately sanitized and
does not distinguish quota/429 from server/5xx in historical logs; exact HTTP
status or provider quota cause cannot be recovered from these logs.

`compare_batch` turns unchanged records into EXISTING. The default standalone
analyzer skips all EXISTING records, even PENDING. This made the backlog stick
across central runs rather than progress as a normal queue. Unobserved records
were also never analyzed. Successful unchanged hashes remain reusable.

Central orchestration now explicitly opts into retrying PENDING/NOT_ANALYZED
records, including retained records outside the current first page or from a
temporarily failed source. Disabled sources are excluded. Standalone analyzer
defaults and unchanged FAILED records retain their prior no-call semantics;
content changes still permit analysis. Observation times are not advanced by
retrying unobserved records. No state reset or schema migration is required.

`ANALYSIS_MAX_CALLS_PER_RUN = 10` limits all new/retry attempts together. Old
pending work is ordered first by first_seen_at and stable notice ID. Complete
SUCCESS/hash matches consume no budget. Deferred work remains PENDING and
makes the run PARTIAL. A 429 pauses further attempts until a new run; other
retryable errors remain bounded by the cap. There are no immediate repeated
calls, sleeps or extra API costs from a retry loop. A continuously unavailable
provider cannot guarantee progression; 10 persistently retryable failures at
the front may hold later work until the service recovers. Permanent FAILED
results need content change or explicit operator intervention rather than
unbounded retries. Numeric HTTP status is now logged without API body/key/model.

Offline persisted-backlog verification (fake provider, no paid calls):
118 PENDING -> 108 -> 98 over two new analyzers, exactly 10 calls per run.
Pipeline storage/feed integration also drains 3 -> 1 -> 0 with cap=2 and
reuses all subsequent SUCCESS records without calls. Tests cover 429 pause,
new-run retry, retained/unobserved backlog and disabled-source exclusion.
Historical provider rejection status cannot be retroactively identified;
these tests establish queue progression when the provider accepts requests.

Stage 1 regression: 450 tests, OK (original 446 plus four image-body cases).
