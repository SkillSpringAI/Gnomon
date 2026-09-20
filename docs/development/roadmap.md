# Gnomon Development Roadmap

## Roadmap status

This document contains future work and planned capabilities. It is not current implementation truth. For what exists now, read [Current Source of Truth](source-of-truth.md). For completed work, read [Development History](development-history.md).

## Near-term hardening

### Ordered authority foundations

The 19 September sequence is baseline/docs → Authority Epoch foundation → verification
and adversarial review → transition actor/reason hardening → stop. Point-of-effect
checks are implemented in `9c82544d` (successful hosted Quality run #12).
The epoch foundation and bounded actor/reason matrix are hosted-verified in `4ea2693`;
see [authority foundations](authority-foundations.md) for the completed scope.

The restrictive recovery-bootstrap entry boundary is implemented; reconciliation,
new-epoch replacement, RecoveryContext, OperatorAuthorization, ExecutionAuthorization
epoch binding, deployment cloning, and backup reconstruction remain deferred.
Backup/restore depends on authority lineage, transition/restoration
authority, bootstrap semantics, and RecoveryContext; it is not the next implementation slice.

The canonical runtime state vocabulary is NORMAL, DEGRADED, COMPROMISED_SUSPECTED,
LOCKDOWN, and RECOVERY_REQUIRED. Historical security vocabulary is not an additional
runtime state machine. Full recovery conformance remains open.

### Closed local slices: interruption and mutation ordering

The [20 September implementation](cycle-closure-authority.md) adds exact-attempt
containment closure, the general outcome guard and runner integration, reversal
authorization, and commit ordering for the five selected writers. Atomic audit and
real PostgreSQL interleaving checks cover the bounded scope.
The [interruption/ordering closure checklist](../archive/completed-slices/2026-09-20-slice-closure-gaps.md)
is closed with runner failure propagation, full preservation snapshots, all
restrictive states, same-task transaction composition and matching hosted evidence.
Cross-task batching remains unsupported. Protected restoration and broader recovery
semantics remain separate.

### Workflow and persistence hardening

- Retained evidence and durable progress are exposed through one read-only latest-attempt projection and the workspace; broader UI redesign remains deferred.
- The reviewed DB-critical authority invariants are constrained by migration 025; broader task/cycle/provider vocabulary constraints remain deferred.
- Recognized database constraint failures now translate through structured diagnostics at reviewed boundaries; broader persistence taxonomy remains deferred.
- Define compatibility behavior for older governed-memory journal formats.
- Obtain hosted verification for each subsequent implementation baseline.

## Future capability phases

### Phase 1 — Investigation and structured planning

Continue improving objective decomposition, hypothesis diversity, evidence requirements, stopping criteria, and review-aware planning. Automatic semantic stopping remains future work.

### Phase 2 — Source retrieval and evidence storage

Add bounded extractors for additional source formats where justified, original-byte storage, historical duplicate reconciliation, and automatic source discovery under explicit policy.

### Phase 3 — Claims and provenance

Expand entity and relationship modeling, claim classifications, evidence weighting, source-dependency graphs, contradiction propagation, and historical epistemic reconstruction.

### Phase 4 — Memory retrieval and reporting

Add cross-task retrieval, semantic synthesis, rebuildable semantic indexes, richer context construction, and report generation that remains grounded in persisted evidence and uncertainty.

### Phase 5 — Memory governance and rollback

Extend governed memory beyond claims and assessments, add dependency-aware reassessment and provenance rollback, and define retention, privileged purge, and recovery operations.

### Phase 6 — Agent-network research method

Strengthen the bounded fake-agent contract, adversarial coverage, agent diversity and dependency modeling, operator visibility, outbound privacy controls, and network isolation semantics.

### Phase 7 — First live external-agent adapter

Only after the hardening gates: add one replaceable platform adapter with secrets-backed identity, discovery, observation, messaging, rate limits, mocked contract tests, enable/disable controls, and no change to core domain authority.

### Phase 8 — Long-running research

Add persistent scheduling, queue or equivalent worker integration, maintenance schedules, task budgets, timeouts, stopping criteria, human approval gates, dashboards, and interruption recovery. Long-running operation must remain bounded and policy-controlled.

## Deferred by design

The following remain deferred unless they remove a blocker or materially reduce risk:

- Multiple live agent networks and broad plugin ecosystems.
- Broad provider expansion.
- Sophisticated autonomous planning.
- Large unrelated UI redesigns.
- Performance optimization without profiling evidence.
- Migration downgrade support unless deployment requires it.
- Additional persistence backends and distributed storage.
- Advanced semantic synthesis and automatic stopping reasoning.
- Full multi-user federation and encrypted shared session storage.

## Cross-cutting gates

Every future phase adds unit, contract, integration, security, migration, recovery, and documentation evidence appropriate to its boundaries. No phase is complete without explicit status, negative tests, concurrency coverage where relevant, migration verification, smoke/prototype checks, and updated conformance records.
