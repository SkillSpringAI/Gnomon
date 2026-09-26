# Interrupted-cycle closure authority

> Dated execution and verification record. Status and remaining-work statements below describe this checkpoint; use the maintained [current source of truth](source-of-truth.md) and [roadmap](roadmap.md) for present claims.

Date: 20 September 2026.
Status: implemented and closed at the 20 September closure checkpoint. The archived
[closure checklist](../archive/completed-slices/2026-09-20-slice-closure-gaps.md)
records the gap-by-gap disposition.
This is bounded containment bookkeeping, not restoration authority. Contracts #1–#5
are unchanged. Checkpoint verification is preserved in the [historical implementation-status journal](../archive/completed-slices/2026-09-26-pre-c1-implementation-status-journal.md).
Baseline: `4ea2693d368eee016b6f0436a0366faf17922c5d`, checkpoint
`checkpoint-2026-09-19-authority-foundations`.

## Implemented decision

Use the existing `SECURITY_CONTAINMENT` capability to authorize a dedicated,
trusted application operation that closes an already-running cycle after security
policy stops its work. Treat this as bounded lifecycle bookkeeping. Keep ordinary
outcome submission and research-result mutation under `MEMORY_MUTATION`.

Capability permission is necessary but insufficient. The closure operation must
also validate the exact task, cycle, running attempt, initiating application path,
and allowed writes. An epoch UUID, attempt UUID, caller-supplied reason, or exception
message is not authority. A model, source, provider, or external agent cannot invoke
this operation by emitting a closure request.

Reuse SECURITY_CONTAINMENT because this operation removes ongoing work and retains
durable evidence. A new broadly safe lifecycle capability would create another
permission surface without solving the scope problem. Requiring MEMORY_MUTATION
for this narrow operation would prevent closure precisely when restrictive states
deny research mutation. Neither approach justifies exempting the general outcome
endpoint from security checks.

## Baseline gaps addressed by this implementation

| Path | Observed behavior at the checkpoint | Consequence |
| --- | --- | --- |
| `SourceCycleRunner.run` | Catches SecurityCapabilityDenied and invokes `recover("blocked")`, which calls `CycleProgress.finish` and `record_cycle_outcome` | Security denial can close a cycle through a general write path; no explicit closure authority is checked |
| `AgentCycleRunner.run` | SecurityCapabilityDenied reaches the generic exception handler, which attempts FAILED closure and re-raises | Security interruption is classified differently from the source runner |
| `ResearchService.record_cycle_outcome` | No security capability check; merges submitted evidence/claim references, summaries and objective results; closes RUNNING attempts for the cycle | Too broad to serve as a containment-only exception; also exposed through the public outcome route |
| `ResearchService.recover_cycle` | Requires MEMORY_MUTATION; closes an attempt as INTERRUPTED, marks cycle FAILED, and can pause the task | Existing operator recovery is unavailable in restrictive states; it is not the proposed closure operation |
| `SqlAlchemyResearchTaskRepository.edit` | Commits lifecycle changes and audit together; labels outcome actor as local_operator | Useful atomicity precedent, but runner containment needs accurate attribution |

Evidence is in `src/research_agent/application/source_cycle_runner.py`,
`agent_cycle_runner.py`, `cycle_progress.py`, `research_service.py`,
`src/research_agent/api/routes/investigations.py`, and
`src/research_agent/persistence/repositories.py`.

The existing `test_mid_cycle_source_authority_revocation_stops_second_fetch`
injects a capability exception. It establishes that a second fetch stops, but does
not establish a persisted lockdown, valid closure authority, epoch attribution,
or parity between runners. The general outcome-path gap is a code-inspection
finding, not a claim that a new adversarial runtime test was executed today.

## Bounded operation requirements

### Implementation lock protocol (recorded before implementation)

All five covered writers use this order: task row FOR UPDATE, canonical security
row FOR SHARE with refreshed validation, then any cycle/attempt/knowledge rows,
then audit append. Locks remain held until the owning transaction commits or rolls
back. Security transitions acquire only the security row FOR UPDATE and never
acquire task rows, so there is no inverse dependency from transition to task.
Task-first ordering also accommodates extraction callers that already hold the
task lock before staging governed memory. No network work runs under these locks.

A writer that obtains the security share lock first commits or rolls back before
lockdown can update the security row. If lockdown wins, the writer's locking read
observes the restrictive state and denies ordinary mutation. Containment closure
remains permitted only through its exact-attempt service. Transactions at stronger
isolation may fail with serialization errors; they must not bypass authorization.
Runner finalization must not flush an attempt update before acquiring the task
lock; the general outcome transaction already finalizes its attempts.

Closure changes only cycle status/completed_at/result_summary/recovery_reason,
attempt status/stage/finished_at/recovery_reason, task updated_at, and one audit
append. All research artifact and objective fields remain byte-for-byte unchanged.
Caller identity is an internal source_runner/agent_runner enum, never an API field.
The request reason is fixed to security_policy_interrupted. An identical repeat
requires the matching audit event and terminal pair; any other terminal state or
caller/attempt mismatch is a conflict. The audit records the observed epoch/version,
not an unimplemented start-epoch authorization claim.

1. Roll back pending research writes before opening the closure transaction.
   Freshly load and validate canonical security state and epoch, and check
   SECURITY_CONTAINMENT. Missing or corrupt authority state denies closure;
   it must never bootstrap an epoch or fall back to a privileged default.
2. Require trusted internal runner context and the exact persisted attempt identity.
   Validate task/cycle ownership and RUNNING attempt plus ACTIVE cycle under fresh
   row locks. Do not close all attempts by cycle number. A missing, conflicting, or
   ambiguous attempt fails closed. Task pause must not itself prevent safe closure.
3. Set the cycle to BLOCKED and its attempt to INTERRUPTED for security interruption.
   These names belong to different existing status vocabularies: INTERRUPTED is an
   attempt status, not a new CycleStatus. Use a transaction-assigned closure timestamp and a bounded
   security-interruption reason. Generate any closure summary from trusted fields.
4. Preserve committed evidence IDs, claim IDs, attempted work, objective results,
   reviews, and provenance. Do not merge new caller-supplied artifacts, promote
   claims, mark objectives resolved, report success, reopen work, change task status,
   or contact an adapter. Preserve existing unresolved work; the implementation
   must specify any conservative addition from the saved plan before writing it.
5. Commit attempt closure, cycle closure, and a dedicated redacted audit event in
   one transaction. Record task/cycle/attempt, trusted actor, bounded reason, prior
   and resulting statuses, and observed security epoch/version. Audit failure rolls
   back the complete closure. Do not label the runner as a local operator.
6. Make an exact repeat idempotent with no duplicate audit. Never overwrite a
   terminal outcome committed by an operator or another runner. Reject it with
   TaskStateConflict; only the exact matching interruption is idempotent. Do not
   claim this operation performed a closure it did not commit.

Canonical epoch attribution here describes authority observed at closure. Current
attempt records have no start-epoch binding; an audit epoch alone cannot prove
continuous authorization since dispatch. Do not claim that guarantee or implement
ExecutionAuthorization epoch binding in this slice. Any future epoch replacement
must establish explicit fencing for old attempts before becoming available.

If canonical authority or storage is unavailable, the process must still stop
external work. Durable closure cannot be claimed. Leave retained records intact
and surface that closure is pending; subsequent privileged reconciliation requires
its own authority. No corrupt-state repair or recovery bootstrap is permitted.

## Implementation sequence and exit evidence

1. Specify the internal request/result and bounded audit schema, exact permitted
   fields, idempotency key, and row-lock order. Review locks against existing
   evidence, lifecycle, recovery and security-transition writers to avoid deadlocks.
2. Implement the dedicated transaction and prove atomic failure behavior before
   connecting runners. Do not expose a public bypass flag or accept arbitrary
   CycleOutcomeCreate through this operation.
3. In one integrated change, route security interruption from both runners through
   the bounded operation and gate the general outcome path with MEMORY_MUTATION.
   Retain normal failure behavior and existing operator recovery semantics. Do not
   ship a general-path guard alone that strands the runner's closure attempt.
4. Verify committed restrictive transitions before fetch/dispatch and after results
   return; no late evidence/claim writes, success outcomes, or additional outbound
   effects. Check retained progress and exactly one correctly attributed audit.
5. Verify all restrictive states; missing/invalid authority; stale or foreign
   attempts; forged scope/reason; cached ORM state; duplicate closure; manual
   outcome races; late results; and audit/database failure. Prove general API
   outcome writes remain denied under restriction while bounded closure succeeds.
   Check memory-backend behavior separately rather than claiming PostgreSQL
   security guarantees for it.

## Implementation and verification mapping

`CycleInterruptionService.close` owns rollback of pending work and the single closure
transaction. Its request accepts only task/cycle/attempt and the trusted runner enum;
there is no public endpoint, outcome payload, reason override, or arbitrary mutation
callback. Scope mismatch and any other finalized outcome raise TaskStateConflict.
The sole idempotent case is the same attempt/caller with its dedicated interruption
audit and matching BLOCKED/INTERRUPTED state. All objective and artifact fields remain
unchanged. Observed epoch/version and exact attempt are recorded in the audit payload.

Both runners catch SecurityCapabilityDenied separately. Their ordinary failure
finalization also redirects to bounded closure if its general outcome write is
security-denied. General outcome writes and memory reversal now require locked
MEMORY_MUTATION. The provisional attempt finish before general outcome was removed:
the outcome transaction already finalizes attempts under its task lock.

The shared `require_locked_capability` helper holds a refreshed FOR SHARE security
row lock to commit/rollback. It is used after the task lock by MemoryService.stage,
MemoryService.reverse, EvidenceService.create_source, ResearchService.record_cycle_outcome,
and bounded closure (with SECURITY_CONTAINMENT). Evidence retains its early unlocked
admission check too; ordering depends on the later locked check. Stage remains a
caller-owned transaction and must be committed or rolled back by that caller.

`tests/integration/test_interruption_ordering.py` covers exact/duplicate/foreign
attempts, terminal conflicts, audit sink rollback, missing/corrupt authority,
retained progress, persisted lockdown during each runner, both manual-outcome race
orders, reversal API/direct denial, and stale cached NORMAL state. It observes
`pg_blocking_pids` across separate PostgreSQL sessions for both race orders of all
five covered paths. Ordinary writers deny when lockdown wins; containment closure
waits and then records the current restrictive authority under its narrow scope.

Runner-level negative coverage now exercises both source and agent runners after
committed progress for a missing canonical authority row, an accurately described
injected invalid-authority load, and closure-audit insertion failure. Every path
propagates the closure error, stops before another fetch/ask, retains committed
evidence, claims, provenance, journal history and attempt progress, leaves the
cycle/attempt ACTIVE/RUNNING, and appends no partial interruption audit. The direct
loader tests remain the evidence for malformed stored epoch representations.

Closure succeeds under DEGRADED, COMPROMISED_SUSPECTED, LOCKDOWN and
RECOVERY_REQUIRED. Its preservation fixture contains nonempty evidence IDs, claim
IDs, objective results, reviews, unresolved and attempted objectives, attempt
artifact lists, source/claim provenance and memory history. The before/after check
allows only the documented cycle fields, attempt fields, task updated_at and one
interruption audit; all other retained records compare exactly. Audit failure uses
the same full snapshot, including task updated_at and underlying retained history.

The complete `MemoryService.stage()` caller inventory is: its public `apply()`
wrapper; `EvidenceService.stage_claim()` (including the same-task extraction batch);
and `AssessmentService.save()`. Direct stage use is otherwise confined to ordering
tests. Every supported production caller operates on one task per transaction.
Tests stage multiple changes for one task under one outer transaction, prove neither
is externally visible before commit, and prove a later-stage conflict followed by
outer rollback removes the earlier staged record and journal entry.

Cross-task batching is explicitly unsupported. A caller must commit or roll back
before selecting another task; no supported caller requires cross-task composition.
This boundary avoids claiming a lock order the implementation does not provide and
does not add a generic multi-task transaction API. The development memory repository
does not gain PostgreSQL security or concurrency guarantees. No claim is made for
direct ORM writers, other lifecycle operations, cancellation of dispatched network
calls, or authority continuity since an attempt started.

## Outside this decision

Protected human restoration, automatic restoration semantics, RecoveryContext,
OperatorAuthorization, epoch replacement, deployment cloning, and backup
reconstruction remain deferred. The separately implemented recovery-bootstrap entry
fence does not broaden this closure operation. Contracts #1–#5 remain untouched.
This document does not authorize restoration or reconciliation implementations.
