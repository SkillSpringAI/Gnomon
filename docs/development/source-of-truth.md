# Gnomon Current Source of Truth

**Implementation HEAD reviewed for C1:** `6be538ed6b32107c0ba69dacb73e8c057d55386b` (documentation-only commit after M2.11).
**Hosted-green C1 baseline:** `8402fbfbf6dc4fc10f8fd3e94154a61f9db364d6`. [Quality run 36211693129](https://github.com/SkillSpringAI/Gnomon/actions/runs/36211693129) tested the committed C1 documentation and passed `checks`, `minimal-install`, and `browser`; the main suite reported 1,819 passed and 28 skipped, and all 28 Chromium browser cases passed separately. The underlying runtime remains unchanged from the pre-C1 implementation baseline.
**Role:** Concise current implementation and gap baseline. The [roadmap](roadmap.md) owns future work, [architecture and governance](../README.md) own normative rules, [implementation status](../conformance/implementation-status.md) owns verification scope, and [development history](development-history.md) owns completed narratives.

**Hosted-verified C2 implementation:** `2740d4a8817b01dd3949ae585788512b1a9dbe4b`.
[Quality run 36278101826](https://github.com/SkillSpringAI/Gnomon/actions/runs/36278101826)
passed `checks`, `minimal-install` and `browser`: 1,848 passed/28 intentional browser
skips in the normal suite, and all 28 Chromium cases passed separately with no skips.
Shared recovery basis construction now lives in
`recovery_authority_basis.py`, and supported inventory reads live in
`recovery_inventory.py`. Context, reconciliation and restoration retain transaction,
lock, capability, freshness, authorization and policy ownership. C2 is formally
closed for this bounded extraction; see the
[C2 closure record](c2-recovery-shared-read-verification.md).

**Hosted-verified C3a implementation:** `0618dec6fb6e0eea2942af2ae9ba672234999882`.
[Quality run 36367975815](https://github.com/SkillSpringAI/Gnomon/actions/runs/36367975815)
passed all three jobs: 1,886 passed/28 intentional browser skips in the normal
suite, and all 28 Chromium cases passed separately. All 35 migrations and the real
PostgreSQL reconstruction variants, including their M2 equivalence assertions,
ran hosted. Reconstruction commits the manifest-derived recovery fence and
`reconstruction_validation_pending` before data import, then clears only that
validation gate after bounded production checks. RecoveryContext capture follows
publication. C3a is formally closed and is the final C3 production slice. A
post-C3a review found the existing private guarded operation sufficient, so C3b
extraction was intentionally not implemented.
See the [C3a closure record](c3a-continuous-reconstruction-fence-verification.md).

**M3a hosted closure:** Implementation
`78a9e408887559e5e100a6f4d22376afee799522` passed
[Quality run 36382958751](https://github.com/SkillSpringAI/Gnomon/actions/runs/36382958751)
across all three jobs: 1,908 passed/28 browser-only skips in normal regression,
28 Chromium cases passed separately, both real reconstruction variants with
C3a/M2 equivalence assertions, distinct PostgreSQL owner/runtime role tests,
and all 35 migrations plus wheel/minimal-install verification. Normal runtime
uses `DATABASE_URL`; migration, backup and complete reconstruction commands
require `OWNER_DATABASE_URL`. M3a is formally closed; M3b has not begun. The
[closure record](m3a-runtime-owner-credential-closure.md) and
[credential procedure](../operations/database-credentials.md) retain evidence,
grants and deployment order. An actual restricted production deployment remains
outstanding; the default local Docker credential is an administrative convenience.

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
| Authority | Governed writes validate current state and required capability; model or external-agent output grants no authority. Runtime/owner URL selection and real-role tests are hosted-verified. | Authentication, deployed role separation, and full incident controls remain open. |
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
| P1 | Runtime and persistence hardening | M3a credential selection and tested grants are hosted-verified; deployed role separation remains an operator requirement. Selected lower-layer constraints, ambiguous-commit evidence, and the audit durability/tamper-resistance decision remain open. M3b has not begun. |
| P1/P2 | Security operations | Authenticated multi-operator authority, full incident containment, scoped isolation, privileged purge, and wider adapter privacy/egress coverage remain open. |
| P1/P2 | Architectural consolidation | C2 shared recovery reads and C3a continuous reconstruction fencing are hosted-verified and closed. C3b extraction was reviewed and dropped; investigation/execution responsibilities, repository/read projections, and invariant verification mapping remain in the M4 programme. |
| P1/P2 | Research expansion | Broader dependency-aware reassessment, semantic retrieval, live external-agent operation, long-running orchestration, and fresh-agent handoff remain deferred to their roadmap gates. |

## Evidence and provenance

- [Implementation status](../conformance/implementation-status.md) records the current verification summary and its limits; the [authority matrix](../conformance/authority-matrix.md) retains requirement traceability.
- The [C1 completion record](c1-documentation-authority-baseline.md) records this documentation reconciliation, local verification, committed SHA, and hosted closure evidence.
- [Development history](development-history.md) and the [M2 sequence](M2%20Incremental%20Implementation%20Sequence.md) link to dated completion records and hosted runs.
- The [pre-C1 current-state journal](../archive/completed-slices/2026-09-26-pre-c1-source-of-truth-journal.md) preserves the former M2.7 closeout record, exact local commands, pending-at-that-time hosted status, and other chronological details. Those checkpoint claims are historical, not current M2 status.
