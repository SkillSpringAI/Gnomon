# M3c Pass 1 — Ambiguous commit exposure and reconciliation

**Status:** Architecture and characterization at formally closed M3b HEAD
`dcdff5a375d1fb0dc2bb6286daa6a213d2c0f21b`. No production behavior,
schema, retry policy, or persistence exception was changed.

The narrow database ambiguity is a COMMIT accepted by PostgreSQL whose
acknowledgement never reaches the caller. An exception before COMMIT, an explicit
constraint rejection, SQLSTATE `40001`/`40P01`, and connection acquisition
failure are different cases. The present code generally cannot determine the
COMMIT phase from the resulting exception. A subsequent `rollback()` cannot
reverse an already accepted COMMIT. A database read on a new connection can
find evidence, but only a stable identity or sufficiently specific transition
history can tie it to the request. The categories below describe **available
evidence**, not permission for automatic retry.

## Transaction and identity inventory

Unless noted, service/repository `Session.commit()` owns the transaction under
the normal PostgreSQL isolation level. Task writers generally take a task-row
`FOR UPDATE` lock; authority writers use the singleton lock. Successful public
audit is staged in the same Session as the governed mutation. A defaulted UUID
is generated when the request is parsed or the service runs: it only helps a
retry if the caller retained or explicitly supplied that exact UUID.

| Group and commit owner | Identity, checks, and durable success evidence | Ambiguous outcome |
|---|---|---|
| Research task creation and lifecycle: repository `save`/`edit`, `ResearchService`, cycle planning/outcome/recovery | Task ID is created by the service; cycle `(task, number)` is unique. `edit` locks task, increments revision and commits task/cycles with generated-ID task events. Cycle activation also creates a durable attempt. Status/fingerprint checks reject stale work. | **2/4.** Task/revision, cycle and event history can show a transition from a known pre-version, but do not generally prove the exact command. A failed create response may lose the new task ID and can be duplicated by a new create. |
| Cycle attempt/progress/interruption: `CycleProgress`, `CycleInterruptionService`, runners | Attempt ID is durable once returned/held. Progress updates attempt, cycle, evidence references and task event in one transaction; its audit ID is generated. Interruption locks task/cycle/exact attempt and compares a prior `CYCLE_SECURITY_INTERRUPTED` event with that attempt and resulting rows before returning a repeat. | **1 conditional** for retained interruption attempt ID and unchanged authority; **2/4** for generated-ID starts/progress and later outcome. A new process needs the attempt ID or a careful task/cycle read. |
| Evidence source/claim and extraction: `EvidenceService`, `ClaimExtractionService`, `AssessmentService` | Task lock; source content/type/URI equivalence lookup, claim statement/link equivalence lookup, generated target IDs; claim and assessment changes use the memory journal. Public audit and source/claim writes share commit. Equal-content reuse can add another audit event. | **2/4.** Content equivalence is not exact command reconciliation; changed metadata or provenance may be hidden by reuse. A caller-held memory `change_id` is stronger. |
| Governed memory: `MemoryService.apply`/caller-owned `stage`, `reverse`; assessment adapter | `change_id` is unique and request/actor/task are compared before apply replay; task lock, target version, current projection, journal and operator audit commit together. `change_id` defaults to a generated UUID. Reversal first looks up any change reversing the original and returns it without comparing the new reversal request. | **1 conditional** for apply with retained `change_id`; reversal duplicate handling is **not exact replay** for a changed ID/reason. A generated ID lost with a response leaves only version/journal investigation. |
| Source registry: `SourceRegistryService` | Unique normalized domain; authority check/lock; row and policy event commit together. `enable` also writes a new policy event when already enabled. Event ID is generated. | **2/4.** Domain/status can show current trust, not which exact register/enable request committed; repeating enable can produce another audit event. |
| Source dependence: `SourceDependenceService.create/mutate/reverse` | Unique `operation_id` in immutable change history; task lock, expected revision, graph checks, canonical command, actor, current projection, change and public audit share commit. Replay compares task/actor/command and returns historical `resulting_state`, even after a later projection mutation. Missing legacy command metadata is rejected. | **1 conditional.** Exact same durable ID and command can distinguish success from conflicting reuse after restart. ID defaults server-side if omitted; replay still requires current capability. |
| Stopping decision: `StoppingDecisionService.decide` | Unique `operation_id`, expected task status/revision and evidence fingerprint; task lock. Decision, change with canonical request, task conclusion and audit share commit. Replay compares task/actor/command and returns historical result. | **1 conditional.** Same retained ID and command prove the recorded outcome even if the current projection later changes; omitted ID is generated and current authority can deny replay. |
| Provider attempt: `ProviderBudgetService.reserve/dispatch/finish/recover` | Caller-held/optional HTTP `Idempotency-Key` becomes unique `operation_id`; task then attempt lock. Each status and event commits together. `finish` equal-status repeat is a no-op; `reserve` duplicate is a conflict. GET exposes status, not a stored normalized reserve command or draft result. | **2/3.** A known ID lets a caller inspect `PENDING`/`DISPATCHED`/`UNKNOWN`/terminal status, but duplicate reserve is not exact semantic replay. The provider effect requires separate treatment below. |
| Provider credential session: route plus `ProviderSessionStore` and `ProviderSessionAuditService` | Token/session ID live only in process memory; database contains redacted, generated-ID CREATE/DELETE events without token/session ID. Create/replacement mutates memory inside a rollback wrapper before DB commit; delete commits audit before deleting memory. | **4.** No durable exact identity or token state survives restart. A lost acknowledgement can leave audit and live token state contradictory; the new characterization tests demonstrate this. |
| Security transition/bootstrap: `SecurityStateTransitionService`, `AuthorityBootstrapService` | Singleton `FOR UPDATE`, expected version/epoch and transition policy. State/version plus generated transition ID/audit commit together. Startup recovery bootstrap is intentionally idempotent while pending. | **2 conditional.** Current state/version and transition history can identify a change at the expected version; later transitions and identical actor/reason requests prevent a universal exact-command proof. No blind transition retry. |
| RecoveryContext and operator/execution issuance: each service-owned `REPEATABLE READ` transaction | Required context/artifact IDs are primary keys; full request command and typed artifact are stored with same-transaction audit. Singleton SHARE lock, basis/epoch/freshness checks. Existing-ID replay decodes and compares the command; changed content conflicts. `replay_id` is stored but is not the unique artifact key. | **1 conditional.** Retained ID and unchanged command give durable historical proof after restart, subject to current read capability/readiness. Historical replay does not renew context or authorization validity. Reconstruction itself generates its context ID internally, so an operator whose call fails may not retain it. |
| Recovery reconciliation | Read-only `REPEATABLE READ` verdict, no governed mutation. | **5** for DB mutation ambiguity. The verdict is not itself a durable completion record. |
| Protected restoration and epoch replacement: service-owned `REPEATABLE READ` transaction | Singleton `FOR UPDATE`, expected basis/version/epoch, context/reconciliation/authorization checks. Restoration and epoch transition audit share commit; `complete_reconstruction` stages restoration and rotation in **one** commit. Caller supplies restoration/replacement IDs and new epoch, but IDs occur inside `related_event_ids` JSON, not unique command rows. | **2/4.** New epoch and version plus both transition rows can support an operator investigation, but direct unchanged replay is rejected once the fence clears and no current service proves an exact request from the JSON IDs. A current `NORMAL` state alone is insufficient. |
| Reconstruction, migrations, backup | C3a fence and readiness are separate `Engine.begin()` commits around child-owned, single-transaction `pg_restore`; each migration and checksum ledger entry commit together under advisory lock. Backup uses filesystem temporary directory/rename; final DB transaction is a read lock/check around publication. | Fence/readiness are **2** with fail-closed residue and discard/recreate, not resumable retry. Migration file name+checksum+ledger provide **1** on rerun. Backup publication is a filesystem outcome, not a DB mutation COMMIT; inspect directory/manifest/digest. |
| Audit-only failure evidence | `AuditService.record_failure()` first rolls back failed success work, then writes a failure event in a new commit with generated event ID. | **4/5.** It never proves the earlier success committed; ambiguity of the independent failure event may duplicate diagnostic evidence but grants no authority. |

## Replay, state, and audit limits

Source-dependence and stopping replay compare canonical request content and
trusted actor as well as the unique operation ID; existing integration tests
cover later projection changes, changed commands and legacy unprovable history.
Memory `stage` similarly compares its unique `change_id`, actor and request.
RecoveryContext and authorization readers compare persisted command/artifact
columns with their same-transaction audit before historical replay. These are
genuine **conditional** reconciliation paths, not merely uniqueness errors.
The caller must have the original ID and request after failure/crash; defaulted
HTTP IDs and internally minted reconstruction context IDs do not guarantee that.
Current capability gates can also deny an otherwise provable historical replay.

The memory reversal shortcut returns a prior reversal of the same original
without checking the new `change_id` or reason; its idempotency is not proof
that the submitted reversal command committed. Provider `reserve` duplicate
returns conflict and the attempt GET reports status, not full command equality.
Security version, task revision and source-registry status are useful reread
evidence, but another actor can subsequently advance or recreate a compatible
state. Transition/audit history improves inference where it identifies the
expected prior version, actor, reason and new state; most generated audit IDs
and non-unique JSON related IDs do not establish exact request identity.

The governed writes identified above stage their normal audit/history in the
same transaction; `record_failure` is deliberately separate. Provider-session
audit and token state span database and process memory and are not atomic. M3's
existing limit remains: a privileged database owner/administrator can alter
rows and audit history; current audit is not administrator-level tamper proof.

## External provider boundary and retry inventory

The report route commits `PENDING`, then commits `DISPATCHED`, rereads
capability, releases the database transaction, calls the generator, and later
commits `SUCCEEDED`, `FAILED` or `UNKNOWN`. If reserve/dispatch COMMIT raises,
this route does **not** reach the provider call, even if the database committed
the marker; a retained operation ID permits status inspection, and overdue
dispatch may be conservatively marked `UNKNOWN`. Once `generator.generate()`
starts, a transport exception does not establish non-execution. The Bedrock
adapter passes no application operation ID/idempotency key to `converse`, has
no provider status lookup, and configures the SDK with up to two attempts.
`ReportGenerationUncertain` records `UNKNOWN` if that database write succeeds;
the provider may already have acted. A known draft followed by ambiguous
`finish(SUCCEEDED)` COMMIT can leave a durable terminal status without a
returned draft, or a `DISPATCHED` row despite an external result. Draft content
is not persisted. Neither case supports automatic re-dispatch.

No production generic database retry loop was found. `pool_pre_ping` checks
pooled connections at checkout, not COMMIT outcomes. Repeated source/memory/
stopping/context/authorization calls are caller-driven and require the
conditions above. Provider attempt `finish`/`recover`, bootstrap and exact
interruption have narrow idempotent branches. The Bedrock SDK retry is an
**external request** retry; absent a provider idempotency contract, it can
reissue a request after an uncertain response. Reconstruction uses strict
pristine-target preflight and discard/recreate after incomplete work. Migration
reruns use checksums. No observed production path catches a lost DB COMMIT
acknowledgement and blindly reruns an arbitrary governed mutation; the risk is
manual/API resubmission with a regenerated ID or the provider SDK's separate
external retry.

SQLAlchemy `DBAPIError` retains `orig`, possible PostgreSQL `sqlstate`,
`connection_invalidated`, statement/parameters and an exception cause where
services use `raise ... from`. Known `40001`/`40P01` are mapped to local
conflicts at recovery/authorization/epoch boundaries. A recognized constraint
name maps through a narrow whitelist; unknown constraints remain raw failures.
Many services otherwise roll back and rethrow, while selected boundaries
normalize broader errors. None records whether COMMIT was sent, accepted, or
acknowledged; `connection_invalidated` proves disconnection, not commit status.
An implementation would minimally need transaction phase, original SQLSTATE/
connection invalidation, and a durable operation ID or authoritative basis to
communicate **possible commit**, without labelling pre-COMMIT failures as
ambiguous or inventing a broad exception hierarchy.

## Characterization and next slice

The existing mocked `commit()`-failure test throws **before** a real COMMIT and
proves rollback only. Two new provider-session tests call the real `commit()`
and then raise a synthetic lost-acknowledgement exception. They show committed
CREATE/DELETE audit with the old credential session still live (including a
DELETE audit claiming revocation). This is deterministic service-level
characterization, **not** a genuine PostgreSQL transport fault. A controlled
TCP proxy that drops only the COMMIT response could test the real boundary, but
the current hosted PostgreSQL service has no such proxy; backend termination
around COMMIT cannot prove whether PostgreSQL accepted it. Do not add a flaky
race and call it proof.

The first implementation slice should be **provider-session-specific
fail-closed handling of uncertain audit commit**: a failed commit acknowledgement
must not leave a credential live when durable audit may record its deletion.
Specify and test the pre-COMMIT versus post-COMMIT behavior and process-restart
limits before implementation; keep secrets out of durable audit. Separately,
document explicit read-before-retry guidance for generated-ID task/evidence
operations and provider attempts. A later, narrow service-specific improvement
could make memory reversal compare the submitted command and improve restoration
outcome inspection. No generic transaction retry or shared reconciliation
framework is justified. The broad M3 assumption that all database failures
are ambiguous is false; ambiguous COMMIT is a narrow phase whose genuinely
unsafe cases depend on operation identity and cross-boundary effects.

**Pass 1 verification:** The focused provider-session, source-dependence,
stopping, context, authorization, provider-attempt, memory, persistence-error,
security-transition and epoch-replacement suites passed (141 tests). Ruff,
changed-file formatting and `git diff --check` passed. The two new tests alter
only characterization coverage; no production code was changed.
