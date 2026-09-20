# Temporary closure checklist — 20 September slices

Status: OPEN. Both slices are implemented locally; neither is declared fully closed.
Base: main at `4ea2693d368eee016b6f0436a0366faf17922c5d`.
Interim tag: `checkpoint-2026-09-20-review-closure-gaps-before-continuing`.
Read this checklist before continuing. The tag preserves unfinished closure work.
Scope: bounded interrupted-cycle closure and the five selected PostgreSQL mutation
paths. This checklist does not authorize additional runtime scope or contract edits.

This is a documentation/code-inspection review, not a new execution of tests.
No new confirmed runtime defect was reproduced in this pass. Distinguish the
verification gaps below from the explicit implementation limits further down.

## Evidence already available

- Broad suite: 1,244 passed, 5 opt-in browser tests skipped.
- Final focused interruption/ordering suite: 30 passed.
- Ruff, strict mypy (79 files), conformance, smoke and real HTTP restart passed.
- Clean-wheel migration/package checks passed before the final missing-row guard.
- Separate-session PostgreSQL tests observe pg_blocking_pids for both race orders
  across memory stage/reverse, source creation, general outcomes and bounded closure.
- Persisted lockdown in source and agent runners retains the first committed result.
- Direct closure tests cover duplicates, concurrent duplicates, foreign attempts,
  terminal conflicts, both manual-outcome race orders, missing authority, injected
  invalid-authority loading, and audit-insert rollback.
- Reversal API and service denial cover every restrictive SecurityState.

These results are useful evidence, but must not be presented as execution of the
uncovered scenarios below. Primary tests: `tests/integration/test_interruption_ordering.py`.

## G1 — Verify the exact final runtime tree

Applies to: both slices. Type: verification gate.

The missing-row early rejection in require_locked_capability was added after the
broad suite and wheel build started. The final focused suite, smoke and restart
passed afterward. The final tree therefore lacks a matching full-suite and clean-
wheel result, even though the earlier results passed.

Close by: after any remaining fixes, run the full quality stack on the final tree,
including full pytest, Ruff, strict mypy, conformance, smoke/prototype and wheel
verification. Record the exact revision/tree and counts. Preserve the five browser
skips as explicit exclusions; do not silently call them passing coverage.

## G2 — Prove failure propagation through both runners

Applies to: Slice 1. Type: integration evidence gap.

Missing authority and audit failure are tested directly against the closure service.
The runner tests cover successful containment after persisted lockdown. They do
not yet demonstrate the complete runner path when closure itself fails. Corrupt
authority coverage injects SecurityStateUnavailable; it does not independently
exercise every corrupt-storage representation through a runner.

Close by: for both source and agent runners, interrupt after committed progress and
exercise unavailable/invalid authority plus closure audit persistence failure.
Assert no successful response or manufactured BLOCKED/INTERRUPTED state, no further
adapter invocation, retained committed data, no partial closure audit, and an
unresolved persisted cycle/attempt where closure did not commit. Use existing
validation tests for malformed epoch representations and describe injected failures
accurately. Do not add automatic reconciliation or bootstrap as a workaround.

## G3 — Complete closure-state and preservation evidence

Applies to: Slice 1. Type: targeted test coverage gap.

Closure tests exercise NORMAL and LOCKDOWN; reversal's all-restrictive-state matrix
does not establish the closure behavior for DEGRADED, COMPROMISED_SUSPECTED and
RECOVERY_REQUIRED. The service preservation test compares the cycle fields outside
the allowed mutation set, but several fields are empty in its fixture. The
persisted() helper compares cycle, attempt and interruption audit; it does not
capture task.updated_at or the full underlying knowledge/provenance history.

Close by: cover closure under each restrictive state; seed nonempty objective
results/reviews, attempt artifact lists and evidence/claim provenance; compare those
records before/after. Extend audit-failure assertions to the task timestamp and
retained knowledge/history as well as cycle/attempt/audit. Assert that successful
closure changes only the documented fields. Do not expand closure's allowed writes
to make the tests pass.

## G4 — Settle and verify the transaction-composition boundary

Applies to: Slice 2, shared lock protocol. Type: explicit scope/contract decision.

The documented protocol assumes one task per transaction. MemoryService.stage is
caller-owned, while the other selected public operations own their commit. Existing
ordering tests call stage once and then commit. They do not establish safe arbitrary
multi-task composition. Acquiring another task lock after holding the shared
security lock can violate the stated task-before-security order; do not infer that
the five-path tests cover that composition.

Close by: inventory the actual stage callers and record that supported batching is
within one task; exercise multiple same-task stages with the lock held until the
outer commit, plus rollback after a later stage fails. Decide whether cross-task
reuse must be rejected explicitly or remains an unsupported internal contract, and
make the code/docs claim consistent. If a current supported caller needs cross-task
composition, stop for a scoped decision rather than redesigning transaction order
silently. No unavoidable deadlock in the tested single-task protocol was found.

## G5 — Obtain checkpoint evidence after local closure gates

Applies to: both slices. Type: checkpoint/hosted verification gate.

The changes are saved in the interim checkpoint named above. Hosted Quality
#13/#14 validate only 4ea2693,
not these slices. Do not reuse those runs as evidence for this implementation.

Close by: once G1–G4 are resolved, update maintained evidence, create the approved
checkpoint, and confirm hosted checks and minimal-install jobs for that exact
commit. The interim tag is not a closure approval; inspect its hosted CI on resumption
and obtain new final-revision evidence after any gap-closing changes.
Do not include the unrelated temporary point-of-effect patch inadvertently.

## Limits to retain, not new blockers to implement

- Runner identity is a trusted in-process enum chosen at the call site. It is not
  authenticated human identity or a persisted proof of which runner began an
  attempt. A raw string is rejected; another trusted Python component can still
  construct an enum. The service is not exposed as an external mutation endpoint.
- Closure audit records the epoch/version observed at closure. Attempts do not
  have start-epoch authorization binding; no continuity-since-dispatch claim applies.
- The ordering guarantee covers the five listed PostgreSQL paths. It does not
  cover direct ORM writes, unrelated lifecycle writers or the development memory
  backend. An earlier unlocked admission check is not the ordering mechanism.
- A running external call is not cancelled by a database security transition.
- RecoveryContext, epoch replacement, backup/restore, OperatorAuthorization,
  protected restoration and new SecurityStates remain excluded.
- Contracts #1–#5 remain unchanged. If a genuine contradiction emerges, report it
  before changing a frozen invariant.

## Closure procedure

Resolve G2/G3 and the G4 contract before the final G1 verification, then complete G5.
For each item, record the test/reference, outcome and any remaining limitation.
Keep status OPEN until the applicable gates have evidence. Once closed, move the
durable results into implementation-status.md and the closure design record, then
archive or remove this temporary checklist through an explicit documentation cleanup.
