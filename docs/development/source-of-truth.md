# Gnomon Current Source of Truth

**Current baseline:** Slice 13 security-state work complete, with Slice 12A/12B verification evidence from 15 September 2026.
**Purpose:** Concise current implementation truth, open release gaps, and immediate work.
**Status:** Current authority for repository state; completed history belongs in [development history](development-history.md), and future work belongs in the [roadmap](roadmap.md).

## Current implementation state

Gnomon is a local-first research API with PostgreSQL persistence, bounded investigations and cycles, deterministic planning, approved HTTP retrieval, conservative claim extraction, provenance, hypothesis assessments, snapshots, reports, governed memory changes, audit events, provider-backed drafts, and a bounded fake-agent research path.

The implemented architecture remains layered across API, application, domain, ports, adapters, persistence, configuration, and security. External models, agents, providers, and sources produce observations, evidence, or proposals; they do not gain authority to mutate governed state merely by producing them.

Current supported behavior includes:

- Investigation creation and retrieval with briefs, hypotheses, questions, plans, cycles, lifecycle controls, and bounded outcomes.
- PostgreSQL persistence with ordered migrations, checksums, fresh bootstrap, populated upgrades, and idempotent reruns.
- Registered-domain HTTP retrieval with redirect, private-address, content-type, size, and deadline controls.
- Exact evidence and claim reuse, provenance links, deterministic claim extraction, and redacted audit events.
- Evidence-aware next-cycle planning with bounded objectives, persisted planning reasons, reviews, evidence fingerprints, and unresolved work.
- Durable cycle attempts, partial-progress retention, operator recovery, late-write fencing, and explicit blocked/failed outcomes.
- Versioned governed memory for claims and hypothesis assessments with actor context, optimistic concurrency, append-only history, and eligible 48-hour reversal.
- Deterministic snapshots and reports that preserve uncertainty, provenance, cycle outcomes, unresolved objectives, and non-authoritative agent comparison metadata.
- Local rule-based and optional Bedrock provider boundaries with idempotent attempts, bounded output limits, dispatch fencing, and explicit unknown outcomes.
- A platform-neutral fake agent network with bounded adversarial scenarios, persisted agent-message evidence, deterministic comparison, and local cycle integration.
- Versioned security state persistence and controlled transitions for the current Slice 13 scope.

## Current guarantees and limits

The following are current guarantees only within the tested and supported scope:

| Area | Current truth |
|---|---|
| Authority | Model and external-agent outputs are proposals or observations, not direct authority. |
| Persistence | PostgreSQL is the reference durable store; migrations are checksummed and drift-rejecting. |
| Memory | Claims and hypothesis assessments use governed proposals, versions, history, audit, and eligible rollback. |
| Cycles | Bounded local runners retain committed evidence and support explicit operator recovery. |
| Providers | Provider work is outside long database transactions; dispatched or uncertain work retains capacity until reconciled. |
| External agents | Only the bounded fake/read-only network is implemented; live outbound networks are not enabled. |
| Security | Current boundary guards, redaction, security-state persistence, and transition tests exist; full incident, authentication, purge, and operational recovery controls remain open. |
| Reports | Reports are derived read-only views and do not establish new knowledge or conclusions. |

No current document should claim full autonomous operation, complete security conformance, semantic memory, live agent networking, backup/restore readiness, or v0.1 release conformance.

## Open P0 and P1 work

| Priority | Issue | Current status | Next evidence required |
|---|---|---|---|
| P1 | Backup and restore conformance | Open | Supported PostgreSQL backup/restore procedure, fixture, state/history/provenance/audit comparison, credential non-persistence checks, and release verification. |
| P1/P2 | Historical journal compatibility | Partial | Define compatibility behavior for older memory journal formats and add reconstruction coverage. |
| P1/P2 | Workflow atomicity observability | Partial | Clearly expose retained evidence and progress in failed-cycle responses and workspace UI. |
| P1/P2 | Lowest-layer invariant enforcement | Partial | Inventory application-only invariants, classify DB-critical rules, and improve understandable database-error translation. |
| P1/P2 | Security-state authority reconciliation | Open | Reconcile the Security Authority state vocabulary with Slice 13’s persisted canonical model and transition table. |
| P1/P2 | Hosted CI evidence | Locally verified | Confirm the expanded verification stack in hosted CI for the working changes. |

The dated architecture review findings are historical evidence. They were reconciled into the current ledger where applicable and should not be treated as the active defect list without checking this document and the conformance records.

## Current exit criteria

The current hardening baseline advances only when:

- Every new governed transition has implementation, positive/negative tests, concurrency coverage where relevant, migration handling, and documentation.
- Backup/restore reproduces authoritative state, history, provenance, versions, audit, and deterministic snapshots.
- Security-state vocabulary and transitions have one reviewed canonical contract.
- CI runs the claimed quality, migration, smoke, packaging, conformance, and relevant integration checks.
- No enabled adapter treats external content as authority or silently converts unknown outcomes into success.
- The authority matrix and implementation status remain synchronized with code and tests.

## Immediate next work

1. Complete backup/restore conformance and recovery documentation.
2. Reconcile the security-state authority documents and Slice 13 implementation.
3. Close workflow observability and database-error translation gaps.
4. Keep live external-agent adapters, broad provider expansion, semantic synthesis, and long-running orchestration deferred until the hardening gates are satisfied.

## Navigation

- [Roadmap](roadmap.md) — future and deferred work.
- [Development history](development-history.md) — completed slices and historical evidence.
- [Conformance](conformance.md) — implementation and release-gate rules.
- [Authority matrix](../conformance/authority-matrix.md) — detailed requirement evidence.
- [Implementation status](../conformance/implementation-status.md) — latest verification summary.
- [Security authority](../governance/security-authority.md) — security requirements and known state-model conflict.
- [Repository documentation inventory](../source_of_truth/repository-documentation-inventory.md) — cleanup classification record.
