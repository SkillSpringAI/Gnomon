# M3c live Bedrock baseline: successful route (Pass 1G)

**Status:** characterization and design only. No additional provider request,
replay, attempt mutation, production status change, or dependency change.

The user reports that operation `90c4307d-0466-4f98-8958-263cb4a40b92`
completed successfully through the existing Gnomon route after correcting
the local dotenv credential formatting and supplied its redacted PowerShell
evidence object. A read-only lookup of this exact operation in the local
PostgreSQL database independently confirmed `SUCCEEDED`, no error reason,
and the three expected ordered audit records. The user reports that the
long-term Bedrock API-key value was entered plainly after removing material
copied from AWS's Windows shell-command representation. This sequence does
not prove the exact cause of either earlier failure.

The durable attempt started at `2026-09-30T03:08:27.455002+00:00` and
finished at `2026-09-30T03:08:36.885395+00:00` (about 9.43 seconds). The
generated audit event records `provider=aws_bedrock`, the configured AU
profile, input/output/total tokens `598 / 455 / 1053`, and local generation
latency `9328 ms`. These durable figures came from selected database columns
and allowlisted audit fields, independently of the supplied PowerShell object.
The same read-only lookup confirmed both preceding operation rows
remain `UNKNOWN / provider_outcome_unknown` with reserve, dispatch, and
uncertain audit events.

The supplied provider observation reports `converse_returned=true`, AWS HTTP
200, request ID `2359bb6c-f8d4-4b26-bf7b-e8ec81272426`, zero SDK retries,
`stop_reason=end_turn`, service latency `8797 ms`, the same `598 / 455 / 1053`
token usage, and `local_parse_succeeded=true`. There was no exception or AWS
error code. The Gnomon caller received HTTP 200, provider `aws_bedrock`, the
configured AU profile, the same usage, and nonempty draft content of length
1426. Total measured route latency was `9937 ms`. These three latency
measurements cover different intervals; their differences do not diagnose
network or parsing overhead.

## What the live test established

The opt-in test creates a synthetic investigation, generates a new UUID for
the `Idempotency-Key`, and calls `POST /investigations/{task_id}/report/draft`
through the production FastAPI application. It requires PostgreSQL and asserts
the selected Bedrock region/model/output and per-task limits. There is no
provider-session cookie, so the route constructs the environment-backed
`BedrockReportDraftGenerator`, using the bearer-only scoped configuration.
The test wrapper observes that generator's real `client.converse` method; it
does not replace the adapter or call an alternate Bedrock client.

The route checks `PROVIDER_DISPATCH` at admission, commits a `PENDING`
reservation and audit, constructs a bounded report snapshot, commits
`DISPATCHED` and audit, checks capability again, and invokes the provider
without a SQL transaction open. The adapter calls `Converse` with the AU
profile as `modelId`, parses the response into a `ReportDraft`, and returns
provider usage when present. On success, the route atomically commits
`SUCCEEDED` and `report.draft_generated`, then returns the draft to the
caller. A passing test asserts HTTP 200, `SUCCEEDED`, ordered audit events
`report.draft_reserved -> report.draft_dispatched -> report.draft_generated`,
provider `aws_bedrock`, configured model, nonempty caller content, and
agreement between caller and audit provider/model and any usage supplied.

This establishes a successful Bedrock Runtime inference through Gnomon's
existing production path with the corrected local configuration. The
isolated harness cleared other AWS credential sources and had no provider
session cookie, so the result strongly supports the intended environment
bearer-key path. The observer deliberately did not capture an authorization
header, and the run does not independently establish key type; the user
identifies the corrected value as a long-term Bedrock API key. The success
followed the formatting correction, but cannot establish the precise cause
of either earlier failure. Operation
`02096537-288c-4cfd-97d9-2bf7d8b16f80` received an explicit non-retried
403 rejection; operation
`46c8bb57-6b53-4dbb-b3dd-24ba419b9322` had no provider diagnostic and
remains genuinely unknown. Neither is changed by this success.

The durable attempt row records identity/status/times/error reason, not draft
text or Bedrock metadata. The generated audit payload holds provider, model,
claim count, provider-reported token counts when supplied, and local
generation latency; the route returns the draft, which is not inserted into
a draft table. The test's `draft_content_persisted=false` evidence field is a
literal assertion about the designed flow, **not** a database-wide content
search. The production adapter derives usage from `Converse.usage`; the audit
copies the validated draft's usage. Its `latency_ms` measures local generation
time, whereas observed `metrics.latencyMs`, if present, measures Bedrock
service latency. Neither must equal total route latency.

## Reconciliation with Passes 1C-1F

**Confirmed:** The isolated environment-backed client can authenticate far
enough to complete a Bedrock Runtime `Converse` invocation of the
documented AU profile from Sydney. Gnomon's authorization checks, durable
reservation/dispatch, adapter parsing, caller response, final attempt state,
and generated audit record work together on this success path. Bedrock's
usage matches caller usage and the audit projection. This invocation needed
zero SDK retries. `DISPATCHED` by itself still proves only that Gnomon
committed its pre-call marker, not that Bedrock executed inference; the 200
response with usage and returned draft is the additional provider evidence
for **this** operation.

**Contradicted:** A general claim that the configured AU profile cannot run
through the Bedrock bearer path, or that this local SDK necessarily requires
CRT for that path, is false. The first client-construction failure came from
an unrelated local AWS profile, and the corrected isolated path completed.
The broad `UNKNOWN` interpretation applied to all adapter exceptions is
also too coarse for the specifically observed non-retried 403 rejection;
that conclusion does not reclassify its historical row.

**Unresolved:** Whether a formatting defect caused the 403 and, if so, which
one; whether it also explains the first diagnostic-free `UNKNOWN`; whether
account policy changed between attempts; and the model's behavior under SDK retries,
timeouts, or lost responses. Success does not provide a status/result lookup
API for an old AWS request ID, prove cost-free rejection, or verify the
candidate minimum SDK version.

## Historical Pass 1G recommendation and later provider-outcome slice

The following was the Pass 1G recommendation before implementation. Pass 3A
subsequently shipped only the exact non-retried boto3
`AccessDeniedException`/integer 403/integer zero-retry classification at
`0bcbc479876903d2382ebbedda50339c5918f1d5`. Its
[closure record](m3c-pass3a-provider-rejection-closure.md) pins the bounded
behavior and hosted verification. The historical operations were not changed.

The existing adapter lets any `Converse` or local parsing exception escape;
`ReportGenerationService` maps it to `ReportGenerationUncertain`, and the
route records `UNKNOWN`. This is conservative for timeouts, lost responses,
retry histories with an uncertain earlier attempt, and opaque failures. The
observed `AccessDeniedException` with HTTP 403 and `RetryAttempts=0` is a
rejected HTTP attempt, not the same evidence class. The smallest proposed
slice is a narrow typed classification at the adapter/service boundary for
**explicit, non-retried, definitive service rejections**. A terminal
`FAILED` outcome with a fixed `provider_request_rejected` reason could use
the existing status vocabulary, while preserving `UNKNOWN` for ambiguous
histories. At the time, this was not yet an implementation decision: `FAILED`
releases draft-budget capacity, `UNKNOWN` retains it, and retries or post-response
parsing failures can still consume provider work. Test the budget effect,
error-code allowlist, SDK retry history, idempotency, and durable audit
before changing behavior. Do not map a final rejection to `FAILED` if an
earlier SDK attempt may have executed and remains unresolved.

Successful request ID, HTTP status, SDK retry count, stop reason, and service
latency are **diagnostic** metadata, not reconciliation proof. The existing
success audit already records provider/model/usage and local latency. There
is no demonstrated need to add the full provider observation to durable
audit. If operational troubleshooting needs correlation, use a small typed,
allowlisted, access-controlled production observation, initially at the
application/logging boundary; decide retention and whether request ID merits
durability separately. Never persist raw AWS messages, headers, credentials,
prompts, response bodies, or draft content as diagnostics.

The boto3/botocore 1.39.0 bearer-support floor remains a separate packaging
verification. A successful run on the installed newer SDK does not prove the
candidate lower bound. Do not couple packaging to outcome classification.

Related records: [Pass 1F access preconditions](m3c-bedrock-access-preconditions.md)
and the [provider-session closure](m3c-provider-session-commit-closure.md). The
[Pass 3 design review](m3c-pass3-provider-rejection-design.md) narrows the
first proposed classification slice to the modeled, non-retried boto3
AccessDenied case and leaves the separate HTTPX session path unchanged.
