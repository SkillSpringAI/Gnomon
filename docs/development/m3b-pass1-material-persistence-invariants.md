# M3b Pass 1 — Material persistence invariant selection

**Status:** Characterization and design at post-M3a HEAD
`f1a547257d1eb6d97fc20f20cc5c5674e636d01a`. No migration, production
constraint, or error translation was changed. This reviews the [M3 Pass 1
matrix](m3-pass1-runtime-persistence-baseline.md) against the 35-migration
schema. The M3a runtime role can perform reviewed DML on application tables,
so a buggy or privileged-but-non-owner runtime writer can bypass Python models;
it cannot add constraints. An owner/admin can still alter both data and schema.
The guarded `pg_restore` is an additional bulk writer for the non-excluded data
tables in this matrix; migrations also establish historical defaults/backfills.

## Candidate matrix

Each row identifies the authoritative columns, supported writers, validation,
database protection, bypass consequence, and relational fit. “Unknown” below
means a value outside the currently supported domain, not a proposed new state.

| Candidate | Current contract and production writers | Invalid persistence and downstream consequence | SQL fit and disposition |
|---|---|---|---|
| Task and cycle lifecycle | `research_tasks.status` and `research_cycles.status`. `ResearchService` changes task/cycle state via `SqlAlchemyResearchTaskRepository`; `StoppingDecisionService` concludes a task; `CycleInterruptionService` directly blocks a cycle. Domain `TaskStatus`/`CycleStatus` and locked transition methods validate supported writes. Task status has a CHECK; cycle number/identity have CHECK/UNIQUE/FK, but cycle status has no CHECK. | Runtime DML can set a cycle to `unrecognized`. Repository `get()` and attempt-progress reads convert it to `CycleStatus` and fail; the entire task can no longer be loaded for ordinary lifecycle, snapshot, or recovery work. The row is fail-closed but operationally uninterpretable. | A named cycle-status CHECK is the first slice. Task-status vocabulary is already protected. Cycle transition ordering, task revision, and one-active-cycle rules belong to locked transaction logic, not CHECKs. |
| Trusted-source status/type | `trusted_sources.status, source_type`; `SourceRegistryService.register/enable` is the writer. Domain `TrustedSourceStatus`/`SourceType` validates commands; unique domain and policy-event vocabularies are constrained, but current-row status/type are not. | Runtime DML can write `status='approved'` or an unknown type. `require_enabled()` selects only exact `enabled`, so the unknown status cannot grant retrieval; list/enable decoding raises. The type also breaks response decoding. This is fail-closed denial, not silent trust. | Simple CHECKs are possible, but defer as a separate registry availability slice; no new trust bypass is demonstrated. A status/timestamp cross-field rule is not established by current domain semantics. |
| Source evidence type | `research_sources.source_type`; only `EvidenceService.create_source` persists it, including retrieval/agent callers. `SourceCreate` validates `SourceType`; no DB vocabulary CHECK. | Direct DML can write an unknown type. Claim extraction converts it to `SourceType`, and snapshot response validation rejects it; evidence cannot be processed or represented, rather than silently becoming another type. | A CHECK is feasible. Defer with the evidence projection family after the control-plane cycle fix; do not add a CHECK solely because the enum exists. |
| Claim and assessment state | `research_claims.status`, `hypothesis_assessments.status`; `MemoryService` is the governed current-row writer, with `EvidenceService` and `AssessmentService` entering through it. Domain `ClaimStatus`/`HypothesisAssessmentStatus` and memory proposals validate writes. Confidence, version, and lifecycle have DB checks, but these statuses do not. | Runtime DML can persist an unknown status. `SnapshotService`/`EvidenceService` typed responses reject it; planning, reporting, stopping readiness, and governed memory reads lose the investigation snapshot. No unknown value is silently treated as “supported.” | Two ordinary CHECKs could prevent this availability corruption. Defer as one evidence-family slice with source/link vocabularies; retain read fail-closed behavior now. |
| Evidence-link vocabulary | `claim_sources.support_type`, `assessment_evidence.relation`; `MemoryService` replaces link sets from validated `ClaimSourceLink`/`AssessmentEvidenceLink`. FKs, pair PKs, and strength ranges exist, but no vocabulary CHECK or same-task composite FK. | Runtime DML can write an unknown relation; snapshot link validation then fails closed. A cross-task link can also be inserted through individually valid FKs; snapshot task filters hide it, while the persisted provenance is misleading/incomplete. | Vocabulary CHECKs are feasible but deferred with evidence. Same-task composite FKs would require unique parent keys, existing-row audit, and a separate provenance decision; do not silently rewrite links. |
| Provider outcome | `report_generation_attempts.status`; `ProviderBudgetService.reserve/dispatch/finish/expiry` owns writes. State-machine checks run under locks; migration 020 CHECK permits `PENDING`, `DISPATCHED`, `UNKNOWN`, `SUCCEEDED`, `FAILED`, `EXPIRED`; operation PK and task FK exist. | DML cannot persist an unknown status. Unknown external outcomes remain intentionally represented by `UNKNOWN`; recovery reconciliation treats unrecognized status as unknown rather than committed, but the CHECK prevents it. | Sufficient value-domain protection. Dispatch/finish order and ambiguous external effect remain transactional/reconciliation concerns. |
| Execution attempt | `research_cycle_attempts.status, stage, task_id, cycle_id`; `ResearchService`, `CycleAttemptProgressService`, and `CycleInterruptionService` write it under task/attempt locks. Migration 015 CHECKs both vocabularies and FKs both identities. | Unknown values are rejected by PostgreSQL. A valid but mismatched task/cycle pair or inconsistent status/stage is still possible by direct DML; attempt readers and recovery could associate it incorrectly. | Existing vocabulary is sufficient. A composite same-task FK is plausible only after auditing existing rows and uniqueness; status/stage transition protocol belongs in transaction logic. Defer relationship hardening. |
| Memory history | `memory_changes.operation, target_type, previous_version, version, reverses_change_id`; only `MemoryService` stages journal rows. Proposal and service validate operation/version/reversal; migrations 007/012 enforce target/operation vocabulary, version adjacency/positivity, unique target version and reversal reference. | Unsupported operation cannot persist. Direct DML can still put malformed or false JSON state/provenance in a formally valid row, making history unreadable or misleading. | Existing scalar protection is sufficient. A broad JSON schema CHECK or polymorphic current-target FK would not prove historical truth and could erase legitimate retained history. |
| Stopping decision | `stopping_decisions.reason, revision, operation_id, evidence_fingerprint, task_id` and `stopping_decision_changes` revisions/command; `StoppingDecisionService` is the writer. Domain request, task lock, evidence fingerprint, exact replay and references are checked. Reason/revision/fingerprint/uniqueness/FK have DB enforcement. | Direct DML can forge semantically stale references or command JSON; typed decision/history reads reject malformed fields, but SQL cannot attest to the snapshot used for the fingerprint. Legacy `command_request` is intentionally nullable and cannot prove replay identity. | Existing relational state is sufficient. Snapshot freshness and command replay belong in locked service logic; no forced backfill of legacy commands. |
| Source dependence graph | `source_relationships` kind/direction/lifecycle/endpoints/revision and `source_relationship_changes`; `SourceDependenceService` is the sole writer. It validates task-scoped endpoints and acyclicity under a task lock. Migration 028 CHECKs vocabularies, direction shape, ordered endpoints and revisions, with composite same-task source FKs, unique identity/revision and reversal FK. | Direct DML can create a directed cycle even with valid rows. Projection marks examined cycles invalid/incomplete rather than silently treating them as independent evidence. A forged JSON history may fail typed read. | Existing row invariants are strong. Graph acyclicity, latest-head consistency and replay are multi-row/transactional; do not encode them as a local CHECK. |
| Authority epoch and transition lineage | `security_state.authority_epoch_id, version` and `security_state_transitions` epoch/version; bootstrap, security transition, reconstruction fence, restoration and epoch replacement are the writers. Domain validates non-nil epoch and locked expected identity. Named DB CHECKs cover singleton/state/version/epoch and transition vocabulary/version; audit history intentionally retains older epochs. | DML can forge a syntactically valid current epoch or omit a transition; a FK from historical transitions to the current singleton epoch would reject valid history, not prove lineage. Current-basis checks reject stale authorizations. | Existing scalar constraints suffice. Atomic transition/audit and epoch rotation remain transaction invariants. No current-epoch FK or generic history trigger selected. |
| RecoveryContext and authorization links | `recovery_contexts`, `operator_authorizations`, `execution_authorizations`, and their audit tables; only `RecoveryContextService.capture` and `AuthorizationService.issue_*` issue them. Pydantic command/basis validators, locked current authority, replay checks, and decode-time column/document/audit comparison apply. UUID/version/expiry/JSON-object CHECKs, execution→operator FK, audit→context FK and artifact PKs exist. | DML can forge a JSON document or a nonexistent caller-supplied `recovery_context_id`; typed decoding and restoration basis checks fail closed. A bare context FK would change the currently permitted caller-supplied ID semantics without proving currentness. | Defer cross-record additions until context-ID semantics are reviewed explicitly. Freshness, fingerprint and same-epoch validity require current locked authority, not static CHECKs. |
| Security/bootstrap/reconstruction shape | `security_state.state, version, authority_epoch_id`, bootstrap origin fields and `reconstruction_validation_pending`; startup/bootstrap, security transition, reconstruction fence/publication, restoration and epoch replacement write the singleton. Loader validates shape and exposes effective `RECOVERY_REQUIRED` while bootstrap is pending. Migrations 024/025/035 enforce named bootstrap/readiness CHECKs. | DML can still forge mutually plausible values, but malformed shape is rejected by SQL or fail-closed loader; a pending fence cannot be interpreted as ordinary current authority. | Existing C3a shape is sufficient for this pass. The validation-pending constraint is not in the generic translator whitelist, but reconstruction wraps SQL failures as reconstruction errors; no caller need for a new category is shown. |
| Authority-bearing command JSON | `recovery_contexts.command`, authorization `command`/document, source/stopping `command_request` and resulting-state JSON; their respective services stage typed canonical commands and compare on replay/read. DB checks mostly require JSON object shape; migrated source/stopping commands may be NULL. | Direct DML can forge embedded IDs/basis while leaving columns unchanged. Context/authorization readers compare typed fields and audit, rejecting mismatch; source/stopping replay cannot claim identity from absent legacy commands. | Selected JSON-to-column CHECKs would be partial and brittle; no general command-schema constraint. Keep typed replay and fail-closed decode. |

## Selection, corruption example, and dependency order

The smallest coherent first implementation set is **one** new constraint:
`research_cycles_status_valid` on `research_cycles.status IN
('planned', 'active', 'completed', 'blocked', 'failed')`. A direct SQL update to
`status='unrecognized'` succeeds today, then `SqlAlchemyResearchTaskRepository.get()`
raises while decoding `CycleStatus`. This makes the whole investigation
unloadable, including ordinary lifecycle and snapshot paths; the new CHECK would
reject that write atomically. The characterization test pins both present facts.
No other vocabulary constraint is included merely because a Python enum exists.

Dependency order after this first control-plane value guard is: (1) assess the
source/claim/assessment/link vocabulary as a cohesive evidence-projection slice;
(2) separately assess same-task evidence-link and attempt identity relationships
against real legacy rows; (3) revisit authorization/context cross-record keys
only after their caller-supplied context-ID semantics are settled. These are
deferred candidates, not automatically approved migrations. Graph acyclicity,
cycle and provider transition graphs, recovery basis freshness, stopping
fingerprints, and audit/epoch atomicity remain transaction or reconciliation
logic, not local CHECKs.

The proposed name is stable for schema diagnostics and migration tests, but no
new public or domain error category is needed. Supported cycle writers emit
known values; a failure would indicate a bug, corrupted direct write, or schema
mismatch. Let the PostgreSQL `IntegrityError` remain an unexpected fail-closed
persistence invariant failure. Do not register it as a duplicate, service
conflict, or generic `INVALID_STATE`; unknown constraint names remain unguessed.

Before a migration, inspect deployed `research_cycles.status` values against
the five-value set. Current domain writers and the checked-in test fixture use
valid values, but this cannot prove every deployed database is clean. A normal
named `ALTER TABLE ... ADD CONSTRAINT ... CHECK` must validate existing rows and
fail on an invalid legacy value; stop for explicit investigation/repair rather
than coercing it. Add a new numbered migration without editing applied files.
The migration runner's transaction and checksum ledger then give atomic
upgrade, no-op rerun, and drift rejection. Verify fresh and populated upgrades,
rejection of invalid pre-existing rows, and installed-wheel resources in Pass 2.

## Pass 1 characterization and verification

Added `test_unknown_cycle_status_is_persistable_but_blocks_task_loading` to
`tests/integration/test_lifecycle.py`. It writes an unknown cycle status within
a rollback-only transaction and proves the repository rejects the row on read;
it does not assert desired future SQL behavior. The focused test passed locally.
No other characterization test was needed: existing SQL migrations and focused
tests already pin the named security, memory, provider, attempt, relationship,
and stopping constraints, while source registry exact-`enabled` selection and
typed response paths make their present fail-closed behavior explicit.

The lifecycle plus persistence-invariant suites passed **26 tests**; migration,
error-translation and persistence-error-boundary suites passed **11 tests**.
Ruff lint and format checks passed on the changed test file. The diff and this
new record passed whitespace checks. No full or hosted regression is claimed
for this characterization-only pass.
