# Gnomon Implementation and Conformance

## Purpose and status

This document is the maintained Markdown form of Gnomon’s implementation and conformance authority. It defines how source code, tests, infrastructure, migrations, adapters, configuration, and future changes demonstrate compliance with the governing authority documents.

Conformance is behavioral and evidence-based. A design document, type annotation, or passing happy-path example does not by itself prove a security, persistence, epistemic, or recovery guarantee.

## Conformance levels

| Level | Meaning |
|---|---|
| 0 — Non-conforming | Violates an authority requirement or lacks a required boundary. |
| 1 — Structurally conforming | Required packages, interfaces, boundaries, configuration, or migration structure exists. |
| 2 — Behaviorally conforming | Tests and implementation evidence demonstrate the required behavior, including relevant failure cases. |
| 3 — Operationally conforming | Deployment, observability, recovery, configuration, and external-environment behavior are verified in the supported operating context. |

The current repository is a progressing implementation baseline, not a blanket Level 3 or v0.1 conformance claim. Each requirement must be classified independently in the conformance matrix.

## Requirement language and traceability

- **MUST** defines a mandatory requirement or invariant.
- **SHOULD** defines a strong default that requires a documented reason to defer.
- **MAY** permits an option without requiring it.

Every normative requirement should trace to its authority source, implementation location, tests or verification evidence, and known limitation. The [authority matrix](../conformance/authority-matrix.md) is the detailed traceability record; the [implementation status](../conformance/implementation-status.md) is the current verification summary.

The source-of-truth hierarchy is: constitutional principles, system architecture, epistemic authority, memory/state authority, runtime/tool authority, research methodology, external-agent authority, security/audit/recovery authority, persistence/data authority, and implementation/conformance authority. Lower-level documents and code cannot silently weaken higher-level requirements.

## Repository and architecture contract

Implementation preserves explicit layers for interface, application, domain, ports, adapters, persistence, configuration, and security. Providers, network platforms, storage implementations, and model SDKs remain replaceable boundaries where practical.

The model and external agents propose or provide information. Deterministic application and domain services validate actions and state changes. Persistence records authoritative state and history but does not alone define epistemic truth. Migrations are versioned and checksummed. API errors, idempotency, concurrency, audit, recovery, and configuration behavior are explicit contracts rather than incidental implementation details.

New features extend the appropriate layer and document any new authority, invariant, assumption, conflict, or migration. A feature must not introduce direct model-to-database writes, unvalidated side effects, provider-specific domain authority, silent historical rewriting, or unbounded execution.

## Evidence and testing pyramid

Conformance evidence should combine:

1. Unit tests for domain rules, validation, parsing, boundaries, and deterministic services.
2. Contract tests for ports, adapters, providers, API schemas, migrations, and error behavior.
3. Integration tests for PostgreSQL transactions, lifecycle, evidence, memory, audit, provider attempts, and recovery.
4. Security tests for authorization, secrets, egress, prompt injection, capability denial, isolation, and redaction.
5. Epistemic tests for provenance, uncertainty, contradiction, independence, claim scope, and historical assessment.
6. Persistence and migration tests for integrity, concurrency, idempotency, drift, fresh bootstrap, and populated upgrades.
7. Adversarial tests for malformed inputs, replay, timeouts, resource exhaustion, malicious providers, agents, and retrieved content.
8. Operational verification for packaging, startup, workspace behavior, backup/restore, supported deployment, and observability.

Tests must cover negative and failure behavior, not only successful paths. A missing external service is not a reason to skip a boundary test when a deterministic substitute can exercise the contract.

## Definition of done

A change is complete only when its scope has:

- A clear requirement and authority relationship.
- An appropriate implementation boundary.
- Deterministic validation for state or side effects.
- Explicit success, failure, blocked, timeout, and unknown outcomes where relevant.
- Provenance, audit, and history behavior where relevant.
- Concurrency and idempotency behavior where relevant.
- Security and privacy review for external or sensitive boundaries.
- Tests covering normal, invalid, adversarial, and recovery paths.
- Updated current documentation and conformance evidence.
- No stale claims in README, roadmap, source-of-truth, or operational guidance.

### Autonomous capability

An autonomous capability additionally requires bounded budgets, external stop authority, policy-validated actions, untrusted-output handling, lifecycle respect, timeout/retry rules, safe recovery, and evidence that the model cannot escalate authority.

### Memory feature

A memory feature additionally requires explicit mutation semantics, actor attribution, provenance, version/history, rollback eligibility, dependency effects, audit, conflict behavior, and protection against silent historical erasure.

### Agent-network feature

An agent-network feature additionally requires identity/trust separation, untrusted observation handling, privacy and secret controls, rate limits, replay behavior, isolation, provenance, and proof that the network cannot change Gnomon authority.

### Research feature

A research feature additionally requires objective and scope preservation, hypothesis and evidence distinctions, counterevidence or contradiction handling where relevant, explicit uncertainty, traceable reports, and an honest stopping reason.

## Implementation status labels

Maintained documents classify capabilities as:

- **Implemented** — current code and tests demonstrate the behavior in the supported scope.
- **Partially implemented** — a bounded subset exists, but the full authority requirement is not met.
- **Planned** — intended future work without sufficient current implementation evidence.
- **Experimental** — available for investigation but not a supported guarantee.
- **Historical** — retained for context and not current authority.

Labels must not be inferred from source presence alone. A feature may be structurally present while behaviorally or operationally non-conforming.

## Change management and drift

Authority amendments are explicit, versioned, attributable, reviewed outside ordinary autonomous operation, and recorded as changes. Architecture drift is investigated rather than normalized through documentation edits. Backward compatibility includes persisted records, migrations, public API behavior, audit history, and recovery semantics where supported.

Security-critical, data-critical, epistemic-critical, and recovery-critical changes require focused tests and conformance review. Documentation must be updated with the code when behavior changes.

## Determinism, observability, and performance

Deterministic rules should remain testable without hidden model reasoning or chain-of-thought dependency. Conformance evidence uses observable inputs, outputs, state transitions, records, and failure outcomes rather than private reasoning traces.

Performance requirements must not weaken authority, provenance, auditability, or safety. Optimization follows architecture and explicit complexity budgets; it does not justify bypassing validation or persistence boundaries.

## Release gate

Before a v0.1 candidate, the repository must maintain:

- Authority traceability for implemented scope.
- Explicit status for every significant capability.
- Behavioral tests for core domain, persistence, security, evidence, memory, provider, agent, and recovery boundaries.
- Migration bootstrap, upgrade, idempotency, and drift verification.
- Packaging and startup verification outside the checkout.
- Redacted audit and failure semantics.
- Hostile-input, replay, timeout, resource, and unknown-outcome tests across enabled adapters.
- Backup/restore and recovery evidence appropriate to the deployment.
- No unsupported claim that the system is fully autonomous, fully secure, or fully conformant.

The current implementation status and authority matrix define the current gap set. The v0.1 gate is not satisfied merely because the current test suite passes; open mandatory requirements remain release work until executable evidence exists.

## Mandatory conformance invariants

1. Authority relationships are traceable.
2. Authority cannot silently drift through implementation or documentation.
3. Model output remains outside direct authority.
4. Capabilities are explicit.
5. Enforcement is deterministic.
6. Providers remain replaceable.
7. Persistence semantics remain independent of one storage implementation.
8. Guarantees are testable.
9. Regressions are protected by tests and checks.
10. Implementation status is explicit.
11. Migrations are safe and verified.
12. Recovery is part of design.
13. Failure semantics are explicit.
14. Autonomy is bounded.
15. Architecture precedes optimization.
16. Deployment evidence counts toward operational claims.
17. Authority amendments are explicit.
18. Historical compatibility is considered.
19. Dependencies remain replaceable.
20. Conformance is behavioral, not merely structural.

## Current verification surfaces

- [Authority matrix](../conformance/authority-matrix.md)
- [Implementation status](../conformance/implementation-status.md)
- [Archived known gaps](../archive/superseded-plans/known-gaps.md)
- [Workspace verification](../operations/workspace-verification.md)
- [Migration operations](../../migrations/README.md)
- [Repository documentation inventory](../source_of_truth/repository-documentation-inventory.md)

The current conformance files remain in their original location during this cleanup. They will be consolidated or archived only after references and verification scripts are updated.

## Related documentation

- [Documentation map](../README.md)
- [Current source of truth](source-of-truth.md)
- [Roadmap](roadmap.md)
- [Architecture overview](../architecture/overview.md)
- [Security authority](../governance/security-authority.md)
- [Persistence authority](../architecture/persistence.md)
- [Original authority document retained during cleanup](../archive/original-authority-documents/Gnomon%20%E2%80%94%20Implementation%20%26%20Conformance%20Authority.docx)
