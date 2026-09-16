# Gnomon Development Roadmap

## Roadmap status

This document contains future work and planned capabilities. It is not current implementation truth. For what exists now, read [Current Source of Truth](source-of-truth.md). For completed work, read [Development History](development-history.md).

## Near-term hardening

### Backup and restore conformance

Build a supported PostgreSQL backup and restore procedure, an automated fixture, and a comparison of IDs, versions, provenance, audit, memory journal, and deterministic snapshots. Verify that provider credentials remain ephemeral and add the recovery check to the release gate.

### Security-state reconciliation

Reconcile the security authority’s `NORMAL`, `DEGRADED`, `ISOLATED`, `SAFE`, and `RECOVERY` vocabulary with Slice 13’s persisted `NORMAL`, `DEGRADED`, `LOCKDOWN`, `RECOVERY_REQUIRED`, and `COMPROMISED_SUSPECTED` model. Establish one canonical state machine, transition table, API contract, and conformance test set.

### Workflow and persistence hardening

- Expose retained evidence and durable progress clearly in failed-cycle responses and the workspace.
- Complete the inventory of application-only versus database-critical invariants.
- Improve translation of database constraint failures into stable API errors.
- Define compatibility behavior for older governed-memory journal formats.
- Confirm expanded verification in hosted CI.

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
