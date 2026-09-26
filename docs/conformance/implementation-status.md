# Gnomon Implementation and Verification Status

**Role:** Current verification summary for the supported implementation scope. [Current source of truth](../development/source-of-truth.md) owns the implementation baseline and gaps; the [authority matrix](authority-matrix.md) owns requirement traceability; [development history](../development/development-history.md) and dated records preserve completed checkpoint detail.

**Implementation HEAD reviewed for C1:** `6be538ed6b32107c0ba69dacb73e8c057d55386b` (documentation-only change after M2.11).
**Hosted-green C1 baseline:** `8402fbfbf6dc4fc10f8fd3e94154a61f9db364d6`. [Quality run 36211693129](https://github.com/SkillSpringAI/Gnomon/actions/runs/36211693129) passed `checks`, `minimal-install`, and `browser`; the main suite reported 1,819 passed and 28 skipped, and all 28 Chromium browser cases passed separately. C1 changed documentation only; its underlying runtime remains the pre-C1 implementation.

The [architectural invariant verification map](architectural-invariant-verification.md) distinguishes executable evidence from documented rules and future recommendations for INV-01–INV-12.

**C1 local verification:** The [26 September completion record](../development/c1-documentation-authority-baseline.md) records passing lint, strict types, traceability, migration, smoke/prototype, and both wheel checks; the normal suite passed with 1,815 passed and 32 skipped, and all 28 browser cases passed separately using Edge. Four host PostgreSQL-client-tool cases were locally skipped and Chromium could not launch on this Windows host; the successful hosted run exercised those four cases and all 28 Chromium browser cases.

## Supported verification scope

| Area | Executable evidence and boundary |
|---|---|
| Security state and capabilities | Unit and PostgreSQL tests cover the five persisted states, structural/actor/reason transitions, stale versions, capability denial, state/audit rollback, and point-of-effect races. This is bounded state-machine evidence, not full incident-response conformance. |
| Execution and governed mutation | Integration tests cover durable cycle/provider attempts, reservation before dispatch, late-result fencing, recovery fingerprints, retained progress, atomic audit, and selected task-then-security lock races. Direct privileged SQL writers and universal cancellation remain outside this guarantee. |
| Memory, source dependence, and stopping | Governed claim/assessment history, eligible rollback, task-scoped source relationships and replay, bounded traversal, and evidence-bound stopping decisions have focused tests. Broader dependency-aware reassessment and historical repair remain future work. |
| M1 recovery authority | The [M1.6 evidence map](../development/authority-epoch-replacement.md#exit-gate-evidence-map) links adversarial tests for bootstrap fencing, fresh context, unknown outcomes, protected restoration, audit rollback, and epoch replacement. [Quality run 35981852013](https://github.com/SkillSpringAI/Gnomon/actions/runs/35981852013) passed at `316c90bf1816743ce73571e907b5c24e4da6cdec` for the bounded local scope. |
| M2 reconstruction and recovery | M2.1–M2.11 completion records and PostgreSQL tests cover backup/restore preflight, canonical equivalence for baseline and restrictive fixtures, recovery entry, reconciliation, atomic restoration/epoch rotation, and credential-sentinel exclusion. The last hosted-green run above covers this supported test-deployment path, not general release readiness. |

The [historical implementation-status journal](../archive/completed-slices/2026-09-26-pre-c1-implementation-status-journal.md) retains earlier commands, results, failures, working checkpoints, and their original limits. In particular, the failed `11c46ae` hosted run and M0 correction remain in the [baseline-restoration record](../archive/completed-slices/2026-09-24-baseline-restoration.md), rather than being erased by the current green status.

## Verification levels

- **Development regression gate:** The [Quality workflow](../../.github/workflows/quality.yml) runs lint, strict typing, migrations, pytest, smoke/prototype checks, conformance traceability, wheel verification, and a separate browser suite.
- **Milestone verification:** A bounded slice closes only with its required focused failure, concurrency, recovery, or hosted evidence at an exact tested SHA. The completion records identify that scope and any skips.
- **Release conformance:** This stronger claim requires the open [release gate](../development/conformance.md#release-gate) and [roadmap](../development/roadmap.md#milestone-10-v01-release-candidate). Green Quality alone does not establish it.

`python scripts/check_conformance.py` checks pinned authority-source hashes, Documents 01–07 section-group coverage, and evidence-reference integrity in the matrix. It does not test runtime behavior or approve a release; Documents 08–10 are pinned for supplemental review.

## Open verification limits

- Deployment authentication and database role separation, ambiguous-commit behavior, full audit durability/tamper evidence, broader incident handling, privileged purge, and live external-agent behavior lack release-level proof.
- M2 has a supported hosted reconstruction/recovery drill. A consolidated operator procedure, remaining adversarial reconstruction cases, and broader deployment/release verification remain open.
- The matrix classifies whole source sections and does not assert a separate behavioral test for each normative sentence. Mixed sections retain their partial or conflicting classification and stated limitations.
