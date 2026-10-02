# M3c Pass 3 — narrow provider rejection classification design

**Status:** historical implementation design. This design pass made no Bedrock
call, attempt mutation, production classification change, durable AWS diagnostic
field, or SDK dependency change. Pass 3A subsequently implemented only its exact
non-retried AccessDenied rule at
`0bcbc479876903d2382ebbedda50339c5918f1d5`, verified by hosted
[Quality run 36668127948](https://github.com/SkillSpringAI/Gnomon/actions/runs/36668127948).
See the [Pass 3A closure](m3c-pass3a-provider-rejection-closure.md) for the
shipped contract. Future-tense and current-behavior statements below describe
the pre-implementation baseline and decision, not today's code.

## Evidence and pre-implementation production contract

The diagnostic-free operation `46c8bb57-6b53-4dbb-b3dd-24ba419b9322`
remains `UNKNOWN`. Operation `02096537-288c-4cfd-97d9-2bf7d8b16f80`
returned a modeled Bedrock `AccessDeniedException`, HTTP 403, AWS request ID,
and `RetryAttempts=0`; Gnomon nevertheless recorded `UNKNOWN`. Operation
`90c4307d-0466-4f98-8958-263cb4a40b92` completed through the same
environment-backed production route: `Converse` returned HTTP 200 with zero
SDK retries, Gnomon parsed a draft, and attempt/audit/caller usage agreed.
The latter is successful-path evidence, not a retrospective diagnosis of the
two earlier operations. See the [successful baseline](m3c-bedrock-successful-baseline.md)
and [access-precondition review](m3c-bedrock-access-preconditions.md).

The route checks provider-dispatch capability at admission and before the
external call, commits `PENDING` and `DISPATCHED` separately with corresponding
audit, releases the SQL transaction, invokes the generator once, then commits
a terminal attempt state with its audit event. The boto3 adapter configures
standard retries with `Config(retries={"max_attempts": 2, "mode": "standard"})`:
two *retries* beyond the initial HTTP request are possible. It lets
`client.converse` and all local parsing exceptions escape. The separate
session-cookie Bedrock adapter uses HTTPX, not botocore; it currently exposes
an HTTP status exception but no modeled botocore error or SDK retry count.
`ReportGenerationService` catches every generator exception as
`ReportGenerationUncertain`; the route records `UNKNOWN` and a fixed reason.

`ProviderBudgetService.finish` locks task then attempt and atomically commits
status plus audit. `UNKNOWN` has no `finished_at`, emits
`report.draft_uncertain`, and counts against the per-task draft limit.
`FAILED` sets `finished_at`, emits `report.draft_failed`, and releases that
capacity. Existing `FAILED` also covers local report validation **after a
provider may have executed**; it must never be redefined as proof of zero
provider work or cost. `reserve` rejects any reused operation ID before the
budget count, even for `FAILED` or `SUCCEEDED`. GET exposes attempt state but
no saved draft; sending the same idempotency key does not replay a prior
response. A new key after `FAILED` can reserve if capacity remains. A failed
final database commit still has its existing persistence ambiguity: this
classification design does not make provider and SQL effects atomic.

## Decision vocabulary for the matrix

- **U:** baseline and continuing fallback `UNKNOWN / provider_outcome_unknown`;
  `report.draft_uncertain`, capacity retained, duplicate ID conflicts. With
  a one-draft limit, a new ID is denied while U remains.
- **R:** eligible for `FAILED / provider_request_rejected` only
  when all strict proof conditions below hold; `report.draft_failed`, capacity
  released, duplicate ID still conflicts, a new ID may reserve. This is a
  rejected request, not proof of zero internal work or charges.
- **L:** provably local/pre-send failure may merit a separate terminal
  failure later, but is **not** a provider rejection. Keep current U for the
  dispatched path in Pass 3A; no attempt exists if construction fails before
  `reserve`.
- **P:** returned successful provider response followed by local failure;
  current U may warrant a separately reasoned `FAILED` later. It is not R.
- **F:** existing `FAILED / report_generation_failed`,
  `report.draft_failed`, capacity released, duplicate ID conflicts.

All R, L, P, and F transitions would use the existing atomic `finish` path,
not a new status or audit mechanism. An inability to commit `finish` must
propagate; it must not trigger another provider call. For every row, a reused
operation ID is a conflict rather than a generation replay.

| Candidate | What Gnomon observes; Bedrock response? | Prior SDK attempts? | Can inference be treated as rejected? | Durable decision and consequences |
| --- | --- | --- | --- | --- |
| Modeled `AccessDeniedException` | boto3 `ClientError`, exact code, expected HTTP 403, response metadata; **yes**. | `RetryAttempts=0` proves no SDK retry in this invocation; missing or positive count does not. | **Yes for that one rejected HTTP attempt** when count is exactly zero. | **R** is justified; first Pass 3A candidate. Otherwise **U**. |
| Other authentication/authorization errors | May surface as `InvalidClientTokenId`, `IncompleteSignature`, `NotAuthorized`, or an HTTPX status; response may exist but these are not the installed Converse operation's modeled rejection set. | May be zero, positive, or unavailable. | Likely denial in some cases, but exact error/transport contract must be vetted; HTTP status alone is insufficient. | **U** in first slice; consider a later allowlist, not the AccessDenied rule by analogy. |
| Invalid request/model | Modeled `ValidationException`/HTTP 400 or `ResourceNotFoundException`/HTTP 404 have service responses. `ModelErrorException`/HTTP 424 is a different processing error. | Check exact retry count. | Validation and missing resource indicate rejection if count is zero; model processing error does **not**. | First two are **R candidates** for a later expansion; 424 is **U**. All remain U in Pass 3A. |
| Throttling | Modeled `ThrottlingException`/HTTP 429 says the request was denied for quota; response exists. | Standard SDK can retry; final count may be positive. | Only a zero-retry modeled denial supports rejection of the logical call. | **R candidate** later if exact zero; otherwise **U**. Keep U in first slice. |
| Quota/service-limit rejection | Converse models `ThrottlingException` for account quotas. Other quota code names are not in the installed Converse error list; 429 also covers `ModelNotReadyException`. | Count may be zero, positive, or unavailable. | Do not generalize from 429 or a generic quota label. | Exact modeled throttling follows the row above; other cases **U** pending separate evidence. |
| Bedrock 4xx generally | Response and status may exist. 408 `ModelTimeoutException` says processing exceeded model timeout; 424 `ModelErrorException` says error while processing; 429 can mean model not ready. | Any count. | **No blanket conclusion** from 4xx. Some errors can follow attempted processing. | **U** unless a specific modeled rejection passes the strict allowlist. |
| Bedrock 5xx | Service response, e.g. 500 `InternalServerException` or 503 `ServiceUnavailableException`. | Often retryable, including possible exhausted retries. | No: service error can occur after remote work. | **U**. |
| Connection failure before response | botocore connection/endpoint exception; no parsed Bedrock response. | May have earlier attempts; metadata may be absent. | Not a provider rejection. A demonstrably pre-send failure could prove no effect for that one attempt, but not through this rule. | **U** now; possible **L** only in a separate pre-send design. |
| Connect timeout | botocore connect-timeout exception; no Bedrock response. | Earlier attempts may have occurred; no reliable final service metadata. | Not a service rejection, even if the timed-out connection sent no request. | **U** now; possible **L** with separate proof and budget policy. |
| Read timeout | botocore read-timeout exception; no final response. | Zero or more earlier attempts may have occurred. | No: request may have reached and run at Bedrock. | **U**. |
| Connection loss after transmission | Transport exception without authoritative outcome. | Zero or more earlier attempts may have occurred. | No. | **U**. |
| SDK retry exhaustion | Final exception/response may include `RetryAttempts>0`, or transport metadata may be absent. | **Yes or unknown**; final response describes only its own attempt. | No without a trustworthy per-attempt proof that each earlier request was rejected. | **U**, even if final error is an otherwise allowlisted 403. |
| Any service error with `RetryAttempts>0` | Final boto3 `ClientError` and metadata; a final denial does not describe all earlier attempts. | **Yes.** | Not for the logical operation under current evidence. | **U**; do not release capacity based only on the last response. |
| Local parameter/configuration error | Client construction may fail before `reserve`; `ParamValidationError` or local serialization may occur after `DISPATCHED` but before an HTTP request. No Bedrock response. | None for proven pre-call failure; otherwise unknown. | No provider rejection. | No attempt for pre-reserve failure; dispatched error is currently **U**, possible **L** separately. |
| Successful `Converse`, local adapter parse failure | A 200 response was returned; adapter then raises while reading text/JSON/building the draft. Current service loses the phase distinction. | Success metadata may report retry count; earlier attempts could still have happened. | No: provider responded successfully. | Current **U**; **P** only after explicit phase and budget review. Not Pass 3A. |
| Successful `Converse`, Gnomon validation failure | Adapter returned a draft; `ReportGenerationService` rejects schema, task/citation relation, or content guard. | SDK retries may have occurred before final success. | No: provider may have executed. | Already **F**. This proves `FAILED` is a failed *draft outcome*, not a no-inference guarantee. |
| Session-cookie HTTPX 403 | HTTP response and `HTTPStatusError`; no modeled boto3 code or `RetryAttempts`. | No SDK retry count; this adapter makes one HTTPX call. | Status alone does not satisfy the narrow modeled proof. | **U** in Pass 3A; first slice must not alter this path. |

AWS's Converse API specifies AccessDenied 403, Validation 400,
ResourceNotFound 404, Throttling 429, ModelTimeout 408, ModelError 424, and
5xx service failures with different meanings. The installed botocore
`Converse` model lists these named errors; it does not list a separate
`ServiceQuotaExceededException`. AWS documents `RetryAttempts` as the SDK
retry count, and `Config.max_attempts` as retries *in addition to* the first
attempt. These contracts support the distinctions above; they do not make
all service error responses equivalent.

## Strict proof rule and narrow typed boundary

For the first implementation slice, only the **environment-backed boto3
`Converse` adapter** may report definitive rejection, and only when all of
the following are observed inside the `client.converse()` exception boundary:

1. Botocore raised `ClientError` for that `Converse` call, with an error code
   exactly `AccessDeniedException` in the installed operation's modeled set.
2. The structured HTTP status is exactly integer `403`, and structured
   `RetryAttempts` is exactly integer `0` (not missing, `False`, a string, or
   a positive value). If either field is missing/malformed/mismatched, retain
   U. A request ID is useful diagnosis but is not required as proof or a
   reconciliation token.
3. Gnomon's adapter/route issued no application-level retry or second
   `Converse` call for this operation. The classifier does not run around
   response parsing or unrelated adapter exceptions.

That evidence is sufficient to say the sole SDK HTTP attempt was explicitly
rejected for insufficient permission, rather than to claim no provider
internal work or charge. It is **not** sufficient when `RetryAttempts>0`:
botocore's final metadata cannot prove what happened on prior HTTP attempts.

A small exception contract in the report-generator port can carry only the
fact of a proven request rejection, with no raw AWS exception text or response
object. The boto3 adapter alone would apply the proof rule and raise it;
`ReportGenerationService` would catch it **before** its broad `Exception`
handler and expose a distinct fixed application error. The route would
catch that error before generic `ReportGenerationError`, call the existing
`finish(..., "FAILED", "provider_request_rejected")`, and return a fixed
redacted error. `EventPayload.reason` would gain only that literal; the
attempt reason column and audit JSON need no migration. All other adapter
exceptions, including HTTPX session errors, continue through the existing
U path. This is a narrow report-generation port contract, not a generic
provider-effect or persistence-reconciliation framework.

No raw AWS `Error.Message`, response body, headers, bearer token, prompt,
draft text, or arbitrary exception representation belongs in the typed
exception, durable attempt/audit, log, or API response. A bounded diagnostic
field can be assessed separately; none is required for this status slice.

## Historical test plan and completed Pass 3A coverage

The design pass added two deterministic **baseline-behavior** tests: modeled
boto3 AccessDenied/403/zero retries then became U and retained budget, while
session-cookie HTTPX/403 remained U. Pass 3A changed the first test to assert
the exact terminal rejection; the HTTPX test still asserts U. Existing
provider-lifecycle tests
already pin atomic final audit, duplicate operation conflict, U budget
retention, F capacity release, late success after operator uncertainty, and
post-provider validation F.

The implementation added focused synthetic tests for exact allowlisted
code/status/zero-retry acceptance; positive, missing, malformed, and boolean
retry metadata failing closed to U; wrong code/status, validation and
throttling codes, and local parsing after a returned response remaining U;
HTTPX session 403 staying U; a single adapter invocation; fixed caller
response; failed audit, capacity release, duplicate-ID conflict, and a
permitted **new** operation after proven rejection. Provider-message
sentinels are absent from the API response and durable audit. Timeout and
connection categories remain on the unchanged broad uncertain path; the
matrix above records their design rationale rather than claiming new
category-specific tests. The historical live IDs are not test inputs.

**Implemented recommendation:** Pass 3A is limited to the observed modeled
AccessDenied/403/zero-retry case on the boto3 adapter. Defer additional
codes, pre-send local failures, HTTPX classification, successful-response
parse failures, provider reconciliation, AWS diagnostic persistence, and the
boto3/botocore dependency-floor change to separately justified work.

In the shipped implementation, `ProviderRequestRejected` is the data-free
reporting port exception, `ReportGenerationRejected` is the application
outcome, and only the boto3 adapter interprets the structured AWS fields.
The classifier surrounds `client.converse()` alone; request construction and
successful-response parsing remain outside it. The route commits the fixed
`FAILED / provider_request_rejected` result through the existing finalizer.
The earlier baseline test expecting `UNKNOWN` for the exact non-retried denial
was updated; the session-cookie HTTPX 403 test still expects `UNKNOWN`.

## Authoritative AWS references

- [Converse operation and modeled errors](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html)
- [Bedrock API error meanings](https://docs.aws.amazon.com/bedrock/latest/userguide/troubleshooting-api-error-codes.html)
- [Boto3 retry count and `Config.max_attempts`](https://docs.aws.amazon.com/boto3/latest/guide/retries.html)
