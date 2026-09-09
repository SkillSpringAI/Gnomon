# Research Agent

A local, single-user research API for persistent investigations, evidence, claims,
and hypothesis assessments. Planning and claim extraction currently use deterministic
logic; the local rule-based provider and optional AWS Bedrock provider are implemented.

## Current capabilities

- Create and retrieve investigations with briefs, hypotheses, plans, and bounded cycles.
- Persist tasks, sources, claims, provenance links, and current hypothesis assessments in PostgreSQL.
- Register and enable source domains, retrieve HTTP sources, and ingest supplied text.
- Extract conservative, unverified sentence-based claims from stored content.
- Read a complete investigation snapshot with explicit uncertainty and source provenance.
- Plan up to three evidence-aware next-cycle objectives with persisted planning reasons.
- Start cycles explicitly and record completed, blocked, or failed outcomes with bounded summaries and evidence/claim IDs.
- Assemble a deterministic read-only report that preserves provenance and uncertainty without generating conclusions.
- Generate a local provider-backed report draft that declares its provider/model and cited record IDs.
- Pause, resume, block, conclude, or abandon investigations with compare-and-set lifecycle controls.
- Inspect redacted, task-scoped audit events for evidence, extraction, retrieval, lifecycle, and cycle operations.

## Local setup

Use Python 3.11 or newer and Docker with Compose. From this directory:

```powershell
python -m pip install -e ".[dev]"
docker compose up -d postgres
```

The default `stub` provider requires no model credentials. To use the optional AWS
Bedrock adapter, install `python -m pip install -e ".[dev,aws]"`, set `LLM_PROVIDER=bedrock`,
set `MODEL_ID` and `AWS_REGION`, and provide AWS credentials through the standard AWS
credential chain or environment variables. Never place keys in source, `.env.example`,
research records, or audit payloads.

For Amazon Bedrock in Sydney, use `AWS_REGION=ap-southeast-2` and
`MODEL_ID=au.anthropic.claude-sonnet-4-6`. This is the Australia geo inference profile
for Claude Sonnet 4.6. See [AWS’s Claude Sonnet 4.6 model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-sonnet-4-6.html)
for current availability and routing details.

For a Bedrock bearer API key in PowerShell, set the AWS-supported environment variable
in the same terminal before starting the API:

```powershell
$env:AWS_BEARER_TOKEN_BEDROCK = "<paste-key-locally>"
```

The boto3 adapter reads that variable directly. The application does not copy it into
settings, prompts, reports, database records, or audit events. AWS documents this
environment-variable flow and recommends short-term keys for ongoing use.

Draft generation is bounded by `LLM_MAX_OUTPUT_TOKENS`, `LLM_MAX_REPORT_CHARS`, and
`LLM_MAX_DRAFTS_PER_TASK` (defaults: 3000, 100000, and 20). The per-task limit is
counted from successful generation audit events; rejected requests record a redacted
budget failure event and do not call the provider.

`GET /provider/status` exposes the active provider, model, region, credential mode, and
limits for a UI status panel. Credential mode is reported only as `stub`,
`bearer_token`, or `aws_default_chain`; the token value is never returned and the
endpoint does not make a provider call.

`GET /provider` serves a small browser panel backed by that status endpoint. It is a
read-only operator surface for local use; it does not accept or store credentials.

`GET /investigations/{task_id}/workspace` provides a lightweight browser workspace for
one investigation. It loads the structured report and can request a draft through the
existing bounded API; it never presents a credential-entry form.

For local-only testing, `POST /provider/session` accepts a short-lived bearer token
from loopback, stores it only in process memory, and returns an HttpOnly session cookie.
`DELETE /provider/session` clears it. This endpoint is intentionally not a multi-user
authentication system; deploy behind an authenticated identity layer before exposing
it beyond the local machine.

After PostgreSQL is ready, apply the SQL migrations in filename order. There is no
version table or automatic migration runner yet. For the current six migrations, in PowerShell:

```powershell
Get-ChildItem migrations/*.sql | Sort-Object Name | ForEach-Object {
    Get-Content -Raw $_.FullName | docker compose exec -T postgres psql -U research_agent -d research_agent -v ON_ERROR_STOP=1
    if ($LASTEXITCODE -ne 0) { throw "Migration failed: $($_.Name)" }
}
python -m uvicorn research_agent.api.app:app --reload
```

Configuration defaults work with the included Compose service; see `.env.example`
for overrides. The health endpoint and unit tests do not require PostgreSQL.
Evidence, assessments, and snapshots require PostgreSQL, including when the task
service is configured to use its development in-memory backend.

Interactive API documentation is available at <http://127.0.0.1:8000/docs>.

The migration command is safe to rerun because the current scripts use additive
`IF NOT EXISTS` operations. It is intended for local development; production rollout
still needs a real migration runner and a recorded schema version.

## Investigation snapshot

`GET /investigations/{task_id}/snapshot` returns persisted state without generating
new conclusions or modifying the investigation:

| Field | Contents |
| --- | --- |
| `task` | Brief, hypotheses, current plan, status, and cycles |
| `hypotheses` | Each brief hypothesis, `assessment_state` (`assessed` or `not_assessed`), and its current assessment or `null` |
| `claims` | All claims in the task, preserving confidence, verification status, and source links |
| `sources` | All sources in the task, including stored content, URI, publisher, and observation time |
| `open_questions` | Questions from the stored plan; no automatic gap analysis |

An assessment's `evidence_links[].claim_id` resolves to `claims[].id`, and a claim's
`source_links[].source_id` resolves to `sources[].id`. Supporting, contradicting,
context, and inferred link classifications retain their stored meaning and strength.
A saved assessment does not promote its underlying claims to verified facts.

The endpoint reads a consistent PostgreSQL transaction and excludes other tasks'
evidence. Hypotheses retain brief order; claims and sources are ordered by timestamp
then ID; links are ordered by their IDs. Unknown tasks return 404 and malformed UUIDs
return 422. An investigation with no evidence returns empty claim/source lists and
explicitly unassessed hypotheses.

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/investigations/<task-id>/snapshot"
```

Snapshots include all stored source text and are not paginated. They are intended
for bounded local investigations. Access control for multi-user deployment is not implemented.

## Evidence-aware cycle planning

`POST /investigations/{task_id}/cycles` plans at most three objectives from saved state.
The deterministic priority order is:

1. Mixed assessments, contradicting evidence links, and contested/contradicted claims.
2. Hypotheses without assessments.
3. Unresolved assessments.
4. Claims requiring verification (including obsolete/retracted claims that need review).
5. Sources without linked claims.
6. Stored open questions, with duplicate questions removed.

A task with no actionable candidates and no sources receives an initial evidence-gathering
objective. With sources and no remaining candidates, it receives an objective to review
stopping criteria. Planning never concludes the task, updates judgments, removes open
questions, executes tools, or adds methods beyond the brief's allowed method list.
Source content is not interpreted as planning instructions.

Each new cycle stores `planning_basis`, aligned with `objectives`: a fixed reason plus
relevant hypothesis, assessment, claim, or source IDs. Earlier cycles retain their saved
objectives and reasons even after assessments change. The first cycle and pre-migration
cycles have an empty basis list. Migration `005_cycle_planning_basis.sql` must be applied
before running this version against another database; it is additive and repeatable.

## Cycle outcomes

Cycles begin as `planned`. Use `POST /investigations/{task_id}/cycles/{cycle_number}/start`
to mark one active, then record a bounded result with
`POST /investigations/{task_id}/cycles/{cycle_number}/outcome`:

```json
{
  "status": "completed",
  "result_summary": "The selected evidence was reviewed and mapped.",
  "evidence_ids": [],
  "claim_ids": [],
  "unresolved_objectives": []
}
```

Outcome status is `completed`, `blocked`, or `failed`; summaries are required. Evidence
and claim IDs must belong to the same investigation. Completed objectives are excluded
from later planning, while unresolved objectives from blocked or failed cycles are
carried forward with an `incomplete_cycle` planning basis. Cycle start and outcome
events are redacted audit records and commit atomically with the cycle change.
Migration `006_cycle_outcomes.sql` adds the durable outcome fields.

## Evidence-aware reports

`GET /investigations/{task_id}/report` returns a structured inventory assembled from
one repeatable-read snapshot. It includes hypothesis assessments (or explicit missing
assessments), claims with source links, citation metadata, cycle outcomes, open
questions, unresolved objectives, and deterministic limitations. It omits full source
content and does not synthesize conclusions; the provider adapters receive this
provenance-preserving model for generated reporting.

`POST /investigations/{task_id}/report/draft` runs the local `rule_based` provider
against that structured report. The draft is not persisted, includes source and claim
IDs used to assemble it, and explicitly states that it does not establish conclusions.
The same provider seam supports the optional AWS Bedrock adapter; credentials and provider
configuration remain outside research state.

Draft output is validated before it is returned: the task ID and cited IDs must match
the structured report, and credential-shaped content is rejected. Successful generation
records a redacted `report.draft_generated` event; provider or validation failures
return 502 and record `report.draft_failed` without exposing exception text.

Cycle planning holds the task row lock while reading evidence. Evidence and assessment
writers use that same lock, so application writes cannot interleave with the planning
snapshot. Brief order and stable snapshot ordering break priority ties. Unchanged gaps
can recur in later cycles; planning an objective does not mark it resolved. Confidence
scores are preserved but are not used as ranking thresholds. This is structural gap
prioritization, not semantic synthesis, independent-corroboration analysis, or automated
stopping-criteria evaluation.

## Investigation lifecycle

`PATCH /investigations/{task_id}/status` takes a desired `status` and the caller's
`expected_status`, for example:

```json
{"expected_status": "active", "status": "paused"}
```

| Current status | Permitted new statuses |
| --- | --- |
| `planned` | `active`, `blocked`, `abandoned` |
| `active` | `paused`, `blocked`, `concluded`, `abandoned` |
| `paused` | `active`, `blocked`, `concluded`, `abandoned` |
| `blocked` | `active`, `paused`, `concluded`, `abandoned` |
| `concluded`, `abandoned` | No further transitions |

Returning to `active` resumes a paused or blocked investigation. Existing creation
still starts tasks as `active`. Concluding is an explicit caller decision; stopping
criteria are not automatically evaluated. An exact retry when the desired status is
already current returns 200 without changing timestamps or adding another event.
Otherwise a mismatched expected status or forbidden transition returns 409. Missing
tasks return 404; missing/invalid request fields return 422. Expected status is a
status comparison, not a general task revision token.

`POST /investigations/{task_id}/cycles` now requires `active`; other states return 409.
PostgreSQL row locks serialize lifecycle changes and cycle creation. Existing cycle
IDs survive subsequent saves, and concurrent cycle creation appends distinct numbers.
Each successful status change or added cycle commits with its audit event; an audit
write failure rolls the change back. Initial task creation/first cycle are not audited
yet. Cycle POST requests remain append operations, not idempotent request replays.

These controls gate new cycle planning. They do not cancel an in-flight fetch or
prevent the existing manual evidence/assessment endpoints from being used. The
in-memory test repository supports transitions without durable audit events.

## Persistent audit trail

`GET /investigations/{task_id}/events?limit=50&offset=0` returns a task's events in
recorded order. The limit is 1-100 and offset must be nonnegative. Unknown tasks
return 404; known tasks without events return an empty list. The existing
`research_events` table from migration 001 is used; no new migration is required.

Recorded event types are `source.created`, `source.reused`, `claim.created`,
`claim.reused`, `extraction.completed`, `extraction.failed`, `retrieval.failed`,
`task.status_changed`, and `cycle.planned`.
Retries create new outcome events while continuing to reuse evidence records.
An operation ID links an extraction's claim events to its completion or failure.
Successful evidence changes and their events commit together. Failed extraction
rolls back staged claims and success events, then records failure in a new transaction.

Payloads contain only generated operation IDs, relevant record IDs, claim counts,
fixed failure reasons, lifecycle states, and cycle numbers. They do not include source text, titles, URLs, credentials,
or raw provider/exception messages. Retrieval failures distinguish domain approval
rejection from other retrieval rejection; detailed failure diagnostics are deferred.

Audit failures are not silently ignored: a success event storage failure aborts the
associated write. If PostgreSQL is unavailable, a failure event cannot be guaranteed;
the request fails rather than claiming successful audit persistence. Unknown-task and
pre-route request-validation failures are not stored as task events. Task creation,
assessment edits, source registry edits, and rejected manual claim submissions are
outside this slice's event coverage. Events are not a complete rollback log or a
tamper-resistant ledger, and deleting a task cascades to its events.

## Retry-safe evidence writes

Source ingestion and fetching reuse the earliest existing source with the same task,
source type, exact URI (including `null`), and exact stored content. Hashes narrow the
lookup, and content equality is also checked. Changes to content, origin, source type,
or task remain separate evidence. A retry does not replace the original title,
publisher, reliability score, or observation timestamp.

Claim creation and extraction reuse the earliest claim with the same task, exact
statement, and unordered set of source-ID/support-type relationships. Confidence,
status, and link strength do not create a new claim or overwrite saved judgments.
Use a future explicit revision workflow to change those judgments. Each source may
occur only once in a claim; duplicate source links return 422.

PostgreSQL task-row locks serialize evidence writes for one investigation using the
application's default READ COMMITTED isolation. Separate tasks remain independent.
Extraction proposes first, then validates and commits the entire batch together;
failure rolls back every staged claim/link. Repeated sentences return one claim.
Concurrent retries and fresh API instances reuse persisted records. Source and claim
POST endpoints retain their existing 201 response contract even when reusing a record.

These are application-enforced identity rules, not new database uniqueness constraints.
All evidence writers must use the service transaction boundary. No migration is needed,
and existing duplicate records are not merged or deleted. Retries choose the earliest
matching record. Different URLs with copied text and differently worded claims still
require future correlation/semantic analysis; record counts do not establish independent
corroboration. Extraction is currently deterministic; a future nondeterministic provider
will need versioned extraction runs or request keys for full operation-level replay.

## HTTP retrieval behavior

`POST /investigations/{task_id}/sources/fetch` checks that the investigation exists
before making a source request. With `REQUIRE_TRUSTED_SOURCES` enabled (the default),
the source registry must permit the initial URL and every redirect destination before
that destination is contacted. Redirect loops and chains beyond five redirects fail.
HTTP(S) URLs with embedded credentials are rejected.

Responses are streamed under a 2,000,000-byte limit and a 500,000-character text limit.
A 30-second retrieval deadline is shared across DNS, connections, TLS, redirects,
and socket reads/writes; each socket operation is also capped at 15 seconds.
Oversized declared lengths fail before reading the body; streamed bytes are also
counted independently of the header. Failed retrievals do not create source records.

Supported formats are plain text and static HTML. HTML text extraction removes
scripts, styles, head metadata, templates, and noscript sections, decodes entities,
and preserves basic block boundaries. It does not execute JavaScript or interpret CSS.
The final URL and HTML title (when present) are stored with the extracted text.
This is basic text normalization, not a full article or browser extraction engine.

PDFs, other media types, binary/null-containing text, empty results, and undecodable
text are rejected with 422. The client requests uncompressed responses and rejects
compressed responses to avoid unbounded decompression. A disallowed domain returns
403; a missing investigation returns 404.

The default transport rejects non-public destinations, including loopback, private,
link-local/metadata, multicast, mapped IPv6, and common IPv6 transition addresses.
Every DNS answer must be public. Connections use validated numeric IPs directly while
preserving the original HTTP Host and TLS certificate identity, avoiding a second
hostname lookup. Redirects use the same network policy. Environment proxies are ignored.

DNS waits respect the deadline. Up to four daemon resolver workers may remain active
while an uncancellable OS lookup finishes; further lookups fail closed when capacity
is exhausted. Socket timeouts shrink with the remaining budget, including during slow
headers and bodies. Normalization checks the deadline before returning but does not
preempt Python parsing mid-operation.

These controls apply to the default transport. Injected clients are a trusted testing
extension and must provide equivalent transport protections if used outside tests.
Network tests exercise the real transport against controlled DNS/socket doubles;
they do not constitute a live deployment or penetration test. Host-level egress rules
remain appropriate defense in depth for deployment.
Retrieved text remains untrusted evidence even after normalization. Original HTML
bytes are not retained yet; retrieval failures are recorded as redacted task events.

## Validation

```powershell
python -m pytest -ra
python -m ruff check .
python -m mypy src
```

The snapshot integration tests require the migrated PostgreSQL database and fail
if it is unavailable. They create isolated task records and delete those records
after each test. Run `python -m pytest tests/unit` for database-free checks.

## Remaining work

- Deeper semantic synthesis, provider cost accounting, and production authentication.
- PDF extraction and bounded compressed-response support.
- Historical duplicate reconciliation, broader audit coverage, and reversible memory changes.
- Automated migrations, richer report synthesis, and agent-network adapters.

See [the roadmap](docs/roadmap.md), [architecture](docs/architecture.md),
[repository structure](docs/repo-structure.md), and
[initial investigation brief](docs/initial-investigation.md).

## Design principles

- Retrieved content and external-agent messages are untrusted data, never instructions.
- Deterministic application code validates and commits state changes.
- Claims preserve provenance, confidence, and support/contradiction relationships.
- Network platforms belong behind replaceable adapters.
- Keep infrastructure small until the prototype demonstrates a need for more.
