# M3c Pass 3A — Provider rejection classification closure

**Status:** Pass 3A is formally closed for its narrow provider-rejection rule.
The production implementation is
`0bcbc479876903d2382ebbedda50339c5918f1d5`. Hosted
[Quality run 36668127948](https://github.com/SkillSpringAI/Gnomon/actions/runs/36668127948)
reported that exact `headSha` and passed `checks`, `browser`, and
`minimal-install`. This documentation record follows the tested code; it does
not close all provider-attempt or external-effect reconciliation in M3c.

The environment-backed boto3 Bedrock adapter reports a definitive provider
request rejection only when a `ClientError` arises from its single
`client.converse()` call with structured `Error.Code` exactly
`AccessDeniedException`, `ResponseMetadata.HTTPStatusCode` exactly integer
`403`, and `ResponseMetadata.RetryAttempts` exactly integer `0`. Boolean values
do not satisfy either integer check. Request construction and successful
response parsing sit outside the classifier. Missing, malformed, mismatched,
or positive-retry metadata, other service errors, transport failures, and
local parsing failures retain `UNKNOWN / provider_outcome_unknown` after
dispatch. The separate session-cookie HTTPX adapter is unchanged; its status
403 alone remains `UNKNOWN`.

The adapter raises a provider-neutral, data-free `ProviderRequestRejected`;
`ReportGenerationService` maps it before its broad uncertain-exception handler
to `ReportGenerationRejected`. The route uses the existing
`ProviderBudgetService.finish` transaction to commit
`FAILED / provider_request_rejected`, `finished_at`, and one
`report.draft_failed` audit event with only a fixed reason. A committed
`FAILED` row no longer counts against the task's draft limit, so a new
operation ID may reserve capacity; the original ID remains permanently
unavailable and is not an idempotent response replay. The budget effect is
derived from the committed status, not a separate mutable counter. A failed
final SQL commit still has its prior persistence ambiguity and cannot justify
another provider call.

This use of `FAILED` means a rejected *draft outcome*. Existing `FAILED`
also includes validation failure after provider execution, so the status is
not proof that no inference work or charge occurred. Pass 3A added no new
status, database migration, durable AWS request ID/status/retry metadata,
raw AWS message, header, credential, prompt, response body, or draft-content
diagnostic. SDK retry configuration, application retry behavior, the
boto3/botocore dependency floor, and provider reconciliation are unchanged.

The design was motivated by two separate live observations. Operation
`02096537-288c-4cfd-97d9-2bf7d8b16f80` received a modeled
`AccessDeniedException`, HTTP 403, and zero SDK retries; Gnomon recorded it
as `UNKNOWN` under the then-current code. Operation
`90c4307d-0466-4f98-8958-263cb4a40b92` later completed a successful
`Converse` call through Gnomon's route after the local bearer-key dotenv
format was corrected. That success does not prove the precise cause of the
earlier 403 or of the diagnostic-free operation
`46c8bb57-6b53-4dbb-b3dd-24ba419b9322`. All three historical attempts
and their audit records remain unchanged. Request IDs retained in the
[access-precondition](m3c-bedrock-access-preconditions.md) and
[successful-baseline](m3c-bedrock-successful-baseline.md) records are
non-secret correlation evidence, not reconciliation handles.

Hosted normal regression reported **1,942 passed, 28 skipped**. All 28 skips
were the opt-in browser cases; provider/report lifecycle tests had no
unexpected skips. The separate Chromium job reported **28 passed, zero
skipped**. The `checks` job applied all **36 migrations**, including 036,
and the prototype rerun was a no-op. Database-wheel verification matched all
36 migration resources and passed schema, populated upgrade, rerun, drift
rejection, and draft checks. The `minimal-install` job passed base-wheel
memory API and provider-status checks without AWS dependencies. Inspection
of hosted logs found no unexpected credential or synthetic provider-message
sentinel exposure. These hosted results contain no live Bedrock inference.

The [Pass 3 design](m3c-pass3-provider-rejection-design.md) retains the
classification matrix and deferred cases. Additional Bedrock error codes,
HTTPX classification, local pre-send failures, successful-response parsing
failures, provider-effect reconciliation, durable AWS diagnostics, and a
separately justified SDK bearer-support floor remain outside this closure.
