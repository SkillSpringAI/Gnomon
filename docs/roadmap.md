# Implementation Roadmap

## Phase 0 — Repository and local foundation

Goal: make the project easy to run and test locally.

Deliverables:

- Python package and dependency management.
- Environment configuration with a checked-in example file.
- FastAPI health endpoint and a CLI entry point.
- Docker Compose PostgreSQL for local development.
- Database migration tooling.
- Formatting, linting, type checking, and test commands.
- Structured logging with request and task identifiers.

Exit criteria: a new checkout can start the API, run migrations, and execute a smoke test without cloud credentials.

## Phase 1 — Investigation brief and structured planning

Goal: prove that the system can create and continue an open-ended investigation safely.

Progress: initial domain models and API slice implemented. PostgreSQL schema and SQLAlchemy wiring are present, and the API now uses PostgreSQL by default. The PostgreSQL API path persists tasks, sources, claims, provenance links, and hypothesis assessments, and the first bounded HTTP retrieval adapter is implemented.

Lifecycle progress: audited compare-and-set status changes now support pause, resume,
block, conclude, and abandon. Only active tasks may plan additional cycles. Row locks
serialize lifecycle/cycle changes, existing cycle IDs are preserved, and tests cover
fresh-session persistence, stale requests, races, and audit-failure rollback. Lifecycle
controls do not interrupt an adapter call already running or enforce stopping criteria
automatically. The local agent runner now acquires a planned cycle exclusively, rejects
overlapping runs across the investigation, and checks lifecycle state between stages
and under the task lock before evidence/claim commits. Partial results survive blocked
or failed runs. Unexpected exceptions attempt a failed outcome before propagating;
process crashes and database outages still require operator recovery. Collection-only
completion preserves every research objective as unresolved.

Agent reports and planning share a single reconstruction path that resolves network
observation references to persisted source IDs. Comparison subjects use exact question
text within each investigation; unknown legacy subjects do not imply agreement or
contradiction. Distinct agent counts do not imply independent evidence. Comparisons
select the latest 100 valid observations deterministically, disclose omitted counts,
and expose a planning reason for reviewing older observations beyond that bound.

Planning completion now matches objective text, reason, evidence identifiers, and a
stored digest of relevant evidence state. Unchanged completed work is suppressed;
new referenced sources, claim versions, or replaced assessments can reopen the review.
Unresolved objectives carry forward from collection-only completed cycles as well as
blocked/failed cycles. Earlier plans are not rewritten; legacy bases without a digest
remain readable and conservatively permit another review. Tests cover fresh-session
continuation, unchanged and unrelated evidence, changed evidence, and explicit completion.

Next-cycle planning now prioritizes persisted counterevidence, missing/unresolved
assessments, claims needing verification, unanalyzed sources, and open questions.
It stores at most three objectives with per-objective reasons and evidence IDs via
migration 005. Earlier plans remain unchanged, and task/assessment locks keep planning
consistent with evidence writes. Cycle start/outcome tracking now persists bounded
results, provenance IDs, unresolved objectives, and audited lifecycle transitions via
migration 006. Semantic synthesis and automated stopping-criteria evaluation remain open.

Deliverables:

- `ResearchBrief`, `InvestigationPlan`, `ResearchTask`, `ResearchCycle`, and `HypothesisAssessment` schemas.
- Support for objectives, hypotheses, research questions, scope, methods, evidence requirements, and stopping criteria.
- LLM provider interface and one provider implementation.
- Strict structured-output parsing and validation.
- Retry and failure handling for malformed or unavailable model responses.
- Task persistence and status transitions, including pause, resume, blocked, and concluded states.
- A minimal endpoint that creates a task and returns the initial plan and task identifier.
- A next-cycle endpoint that proposes bounded follow-up work from the current task state.

Exit criteria: a brief such as “test whether agent networking improves research coverage for AI infrastructure case studies” produces a persisted investigation with hypotheses, questions, methods, stopping criteria, and a first bounded cycle. The task remains open for later cycles.

## Phase 2 — Source retrieval and evidence storage

Goal: gather reproducible source material.

Cycle integration: `run-sources` now maps up to two operator-supplied URLs to saved
objective indexes, acquires a cycle exclusively, and uses the existing bounded HTTP
adapter and deterministic claim extractor. Attempted objectives, retained evidence,
and unresolved work flow through outcomes and reports into subsequent planning.
Integration tests cover the real registry with controlled transport, redirect rejection,
partial failure, pause during retrieval/extraction, retries, and cross-run exclusion.
Source execution is initiated through the API; automatic URL discovery remains open.

Progress: HTTP retrieval now validates enabled-domain policy before each request,
including redirects, streams response bodies under byte limits, caps normalized text,
and rejects redirect loops and unsupported formats. Static HTML is normalized to text;
PDF and compressed responses are explicitly rejected pending bounded extractors.
Tests cover policy rejection without contacting the redirected host, stream cutoff and
closure, text normalization, and persistence only after successful retrieval.
A second retrieval pass adds socket-bound public-address validation and a shared
30-second deadline, including bounded DNS waits and shrinking socket timeouts.
Controlled DNS/socket tests verify IP pinning, Host/TLS identity, private-address
rejection on redirects, and slow-header/body cutoff. Exact source retries now reuse persisted records under task-row locks, including
concurrent fetch/ingestion requests. Claim writes and deterministic extraction also
reuse exact statement/provenance identities, and extraction batches commit atomically.
Evidence writes and reuse, extraction completion/failure, and retrieval rejection now
produce persistent, redacted task events, exposed by a bounded events endpoint.
Success events commit with their writes; extraction failure events are saved after
rollback. Tests cover durability, concurrent retry outcomes, event ordering, redaction,
and rollback when event storage fails. Original-byte storage and historical duplicate
reconciliation remain open; audit coverage for other mutations is still future work.

Deliverables:

- `Source` schema and repository.
- Explicit retrieval tool interface.
- Source content hashing and duplicate detection.
- Raw source storage abstraction.
- Source size, timeout, content-type, and domain policy limits.
- Retrieval errors represented as task events rather than hidden failures.

Exit criteria: a research task can retrieve approved sources and retain enough metadata to reproduce what was observed.

## Phase 3 — Claims and provenance

Goal: transform source material into auditable structured knowledge.

Deliverables:

- Entity, claim, relationship, and claim-source schemas.
- Claim extraction with schema validation.
- Support, contradiction, and inference classifications.
- Confidence and status transition rules.
- Queries for claims by entity, source, status, and confidence.

Exit criteria: every accepted claim can be traced to its source material, and unsupported model assertions are not silently promoted to facts.

## Phase 4 — Memory retrieval and reporting

Goal: make stored knowledge useful in later research.

Progress: deterministic `GET /investigations/{task_id}/snapshot` and
`GET /investigations/{task_id}/report` endpoints now read
persisted briefs, plans, cycles, hypotheses, current assessments, claims, and sources.
The report preserves link classifications, confidence, verification status, stored open
questions, cycle outcomes, and explicit limitations while omitting raw source content.
The local `rule_based` provider and optional AWS Bedrock provider can generate unpersisted
provider metadata and cited record IDs. Draft output validation, redacted success/failure
events, and rollback-safe provider failure handling are covered; external semantic
synthesis remains open. Configurable output, input-size, and per-task draft limits now
bound provider spend before a live call.
The non-secret `GET /provider/status` endpoint exposes the active model, region,
credential mode, and limits for a future UI without exposing credentials.
The local investigation workspace can display a report and request a bounded draft;
credential entry remains intentionally deferred until a production authenticated session design exists.
The local-only session bridge now provides a bounded in-memory bearer-token path for
testing; multi-user federation and encrypted session management remain open.
PostgreSQL integration tests cover fresh-app retrieval, assessment replacement, empty
investigations, unknown IDs, cross-investigation evidence rejection, and report
provenance. Cross-task memory search, generated synthesis, and semantic retrieval remain open.

Deliverables:

- Keyword and relational retrieval first.
- pgvector embeddings only after the non-semantic path is reliable.
- Context builder that includes provenance and uncertainty.
- Report schema with evidence, conclusions, open questions, and citations.
- Report generation from persisted state.

Exit criteria: a later task can retrieve relevant prior claims and generate a report that preserves uncertainty and provenance.

## Phase 5 — Memory governance and rollback

Goal: make consolidation safe and reversible.

Deliverables:

- Explicit memory-change proposal schema.
- Deterministic validation service.
- Event log with previous-state snapshots.
- Archive, merge, restore, and logical-delete operations.
- 48-hour rollback worker or scheduled job.
- Tests for idempotency, stale versions, dependent claims, and rollback conflicts.

Exit criteria: a merge or archive can be undone within the retention window, and the audit trail explains what changed and why.

## Phase 6 — Agent-network research method

Goal: use external agents as a controlled research method without coupling the core to one platform.

Progress: local fake networking, neutral agent contracts, bounded policy, inert evidence
ingestion, deterministic comparison, cycle execution, and a browser workspace are
implemented. The runner rejects overlapping cycles, checks lifecycle state between
stages, retains partial results, and records blocked/failed outcomes. Reports resolve
duplicate observation references to persisted sources, compare matching exact-question
subjects, disclose comparison omissions, and preserve unresolved work. Live network
adapters, secrets-backed identity, outbound messaging, and production authentication
remain open.

Deliverables:

- Agent identity and observation schemas.
- `AgentNetwork` interface.
- Research questions that can be sent to selected agents.
- Agent roles such as source finder, domain specialist, critic, and case-study participant.
- Untrusted-message ingestion pipeline.
- Separate agent-sourced claims and reputation observations.
- Outbound message policy, rate limits, and audit events.
- Fake adapter for local tests.

Exit criteria: an investigation cycle can ask external agents targeted questions, record responses as agent-sourced evidence, compare responses, and seek independent corroboration. Agent messages can never become executable instructions.

## Phase 7 — Moltbook adapter

Goal: connect the abstract networking layer to Moltbook.

Deliverables:

- Authentication and identity handling through secrets management.
- Discovery, observation, posting, and messaging adapter methods.
- Platform-specific rate limits and error mapping.
- Contract tests using mocked API responses.
- Operational controls for enabling or disabling the adapter.

Exit criteria: Moltbook can be enabled as one replaceable research source and communication channel without changing core domain code.

## Phase 8 — Long-running research

Goal: support autonomous continuation under explicit user-controlled limits.

Deliverables:

- Persistent subtask scheduling.
- SQS or equivalent queue integration.
- EventBridge maintenance schedules.
- Per-task budgets, timeouts, and stopping criteria.
- Human approval gates for external communication or sensitive actions.
- Operational dashboards and failure recovery.

Exit criteria: a research objective can resume after interruption while respecting task budgets, tool policy, and approval boundaries.

## Cross-cutting quality gates

Every phase should add:

- unit tests for deterministic logic;
- contract tests for adapters;
- integration tests for database behavior;
- structured audit events;
- security tests for prompt injection and unauthorized tool/state changes;
- migration and rollback checks;
- documentation of new operational assumptions.

## Later-stage circle-backs

- Add migration checksums, downgrade handling, and release integration around the version table.
- Replace the loopback provider session bridge with authenticated identity and encrypted shared storage.
- Add explicit provider rate cards before presenting monetary cost estimates.
- Revisit semantic synthesis, corroboration, and stopping-criteria evaluation after the evidence and report boundaries mature.
