# Gnomon Current Source of Truth

**Implementation HEAD reviewed for C1:** `6be538ed6b32107c0ba69dacb73e8c057d55386b` (documentation-only commit after M2.11).
**Hosted-green C1 baseline:** `8402fbfbf6dc4fc10f8fd3e94154a61f9db364d6`. [Quality run 36211693129](https://github.com/SkillSpringAI/Gnomon/actions/runs/36211693129) tested the committed C1 documentation and passed `checks`, `minimal-install`, and `browser`; the main suite reported 1,819 passed and 28 skipped, and all 28 Chromium browser cases passed separately. The underlying runtime remains unchanged from the pre-C1 implementation baseline.
**Role:** Concise current implementation and gap baseline. The [roadmap](roadmap.md) owns future work, [architecture and governance](../README.md) own normative rules, [implementation status](../conformance/implementation-status.md) owns verification scope, and [development history](development-history.md) owns completed narratives.

## Current implementation

Gnomon is a local-first research API with PostgreSQL as its reference durable store. API, application, domain, ports, adapters, persistence, configuration, and security have explicit package boundaries. Models and external content can supply observations or proposals; deterministic services decide whether governed state changes.

The supported local scope includes:

- Investigations, briefs, hypotheses, questions, bounded cycles, lifecycle controls, evidence, conservative claim extraction, provenance, assessments, deterministic planning, snapshots, and reports.
- Registered-domain HTTP retrieval with network and response bounds; source and fake-agent cycle runners with durable attempts, retained committed progress, exact-attempt fencing, interruption closure, and freshness-bound operator recovery.
- Governed claim and assessment memory with versions, append-only application history, audit, optimistic conflict checks, and eligible rollback. Source-dependence relationships and stopping decisions have bounded, task-scoped command/history and read-projection contracts.
- Local rule-based and optional Bedrock provider drafts with durable reservation and dispatch fencing, budgets, redacted audit, explicit unknown outcomes, and reconciliation. The fake agent network is bounded; live external-agent platforms are not enabled.
- Five persisted global SecurityState values: `NORMAL`, `DEGRADED`, `COMPROMISED_SUSPECTED`, `LOCKDOWN`, and `RECOVERY_REQUIRED`. Versioned transitions, actor/reason checks, direction-aware capability policy, and point-of-effect guards are implemented for reviewed paths. Recovery bootstrap, AuthorityEpoch, exact execution attempt, and recovery fingerprint remain distinct.
- M1 recovery authority for the bounded local scope: a restrictive bootstrap fence, fresh RecoveryContext, supported-evidence reconciliation, separate operator/execution authorization, protected restoration, and epoch replacement.
- M2 backup and reconstruction for the supported PostgreSQL test-deployment path: manifest and state inspection, guarded backup/restore, canonical and restrictive-fixture equivalence, recovery entry, protected restoration with atomic epoch rotation, and credential-sentinel verification. M2 is functionally established with bounded consolidation remaining.

## Current guarantees and limits

| Area | Supported guarantee | Material limit |
|---|---|---|
| Authority | Governed writes validate current state and required capability; model or external-agent output grants no authority. | Authentication, privileged database-role separation, and full incident controls remain open. |
| Persistence | Ordered checksummed migrations, reviewed atomic state/history/audit writes, attempt identities, and bounded failure handling. | Direct privileged database writes, broader constraint coverage, ambiguous commits, and cryptographic tamper evidence are not covered by these guarantees. |
| Execution | Current source, provider, and fake-agent paths use bounded attempts and preserve explicit failure or unknown outcomes. | No live external-agent adapter, generic autonomous runtime, or universal cancellation guarantee exists. |
| Recovery | Reconstructed state enters a separate recovery-bootstrap fence; supported reconciliation and authorization precede restoration and fresh epoch use. | Supported inventory is bounded; wider deployment recovery and full operational procedure remain separate work. |
| Research | Structured evidence, provenance, uncertainty, current reviews, and derived reports survive supported workflows. | Semantic memory, full dependency-aware reassessment, causal independence inference, and unrestricted historical repair are not implemented. |

No blanket autonomous, complete security, general backup/restore readiness, or v0.1 release-conformance claim follows from hosted Quality being green. `SAFE` is not a persisted global state; `ISOLATED` remains a future scoped-containment concept. See the [security authority](../governance/security-authority.md#security-state-and-containment).

## Material open work

No P0 is identified in this reviewed documentation baseline. These P1 or P1/P2 areas remain bounded by the [roadmap](roadmap.md) and release gate:

| Priority | Gap | Current boundary |
|---|---|---|
| P1 | Deployment and release conformance | The M2 reconstruction/recovery drill is hosted-verified for its supported test deployment. A consolidated operator procedure, remaining adversarial cases, broader deployment evidence, and release review remain open. |
| P1 | Runtime and persistence hardening | Normal runtime database privileges, selected lower-layer constraints, ambiguous-commit evidence, and the audit durability/tamper-resistance decision remain open. |
| P1/P2 | Security operations | Authenticated multi-operator authority, full incident containment, scoped isolation, privileged purge, and wider adapter privacy/egress coverage remain open. |
| P1/P2 | Architectural consolidation | Shared recovery reads, reconstruction mechanics, investigation/execution responsibilities, repository/read projections, and invariant verification mapping remain the confirmed M4 programme. |
| P1/P2 | Research expansion | Broader dependency-aware reassessment, semantic retrieval, live external-agent operation, long-running orchestration, and fresh-agent handoff remain deferred to their roadmap gates. |

## Evidence and provenance

- [Implementation status](../conformance/implementation-status.md) records the current verification summary and its limits; the [authority matrix](../conformance/authority-matrix.md) retains requirement traceability.
- The [C1 completion record](c1-documentation-authority-baseline.md) records this documentation reconciliation, local verification, committed SHA, and hosted closure evidence.
- [Development history](development-history.md) and the [M2 sequence](M2%20Incremental%20Implementation%20Sequence.md) link to dated completion records and hosted runs.
- The [pre-C1 current-state journal](../archive/completed-slices/2026-09-26-pre-c1-source-of-truth-journal.md) preserves the former M2.7 closeout record, exact local commands, pending-at-that-time hosted status, and other chronological details. Those checkpoint claims are historical, not current M2 status.
