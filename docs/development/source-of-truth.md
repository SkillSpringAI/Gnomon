# Gnomon Current Source of Truth

**Committed baseline:** `2fb0710` (license update). The closing Slice 2/3 changes are locally verified in the current uncommitted working tree; no hosted Quality run or closing SHA is claimed for that tree.
**Current slice:** Bounded interrupted-cycle closure, retained-progress observability, and stable persistence-error boundaries are locally closed. See the implementation status for exact local evidence.
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
- A read-only latest-attempt progress projection and workspace surface for retained evidence, claims, stages, timestamps, objective state, and unresolved active cycles.
- Versioned governed memory for claims and hypothesis assessments with actor context, optimistic concurrency, append-only history, and eligible 48-hour reversal.
- Deterministic snapshots and reports that preserve uncertainty, provenance, cycle outcomes, unresolved objectives, and non-authoritative agent comparison metadata.
- Local rule-based and optional Bedrock provider boundaries with idempotent attempts, bounded output limits, dispatch fencing, and explicit unknown outcomes.
- A platform-neutral fake agent network with bounded adversarial scenarios, persisted agent-message evidence, deterministic comparison, and local cycle integration.
- Versioned canonical security state persistence, controlled transitions, and centralized capability policy.
- Point-of-effect enforcement for `READ_AUDIT` on audit/history reads, source retrieval in the cycle runner, and provider dispatch after reservation. Admission alone does not authorize a later effect.
- Authority Epoch persistence and epoch-bound new transition audit records, with fail-closed lineage loading and no runtime epoch creation.
- Explicit transition actor/reason authorization and REDUCE/PRESERVE/BROADEN classification of current capability sets. See [authority foundations](authority-foundations.md) for the matrix and limits.
- Direction-aware `AUTHORITY_ADMINISTRATION`: containment cannot broaden, recovery
  is not a superuser capability, and recovery purpose cannot replace authorization
  for the actual authority-bearing effect.
- Startup distinguishes pristine fresh bootstrap, authority-preserving continuation,
  and recovery bootstrap. Recovery entry becomes effectively RECOVERY_REQUIRED before
  requests, keeps restored active-looking records inert, and exposes no reconciliation
  or restoration-completion path.
- Recognized PostgreSQL integrity failures are translated at reviewed write boundaries
  using structured constraint diagnostics; unknown failures remain unexpected, and
  public authority-invariant responses are generic and redacted.

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
| P1 | Backup and restore conformance | Deferred behind authority lineage, transition/restoration authority, bootstrap semantics, and RecoveryContext | Supported PostgreSQL backup/restore procedure, fixture, state/history/provenance/audit comparison, credential non-persistence checks, and release verification. |
| P1/P2 | Historical journal compatibility | Partial | Define compatibility behavior for older memory journal formats and add reconstruction coverage. |
| P1/P2 | Workflow atomicity observability | Closed locally | Latest-attempt read projection and workspace rendering expose retained progress without observation-side mutation; hosted verification remains pending. |
| P1/P2 | Lowest-layer invariant enforcement | Closed locally for reviewed scope | Migration 025 constraints and bounded translation cover reviewed authority/duplicate paths; broader lifecycle and memory vocabulary constraints remain deferred. |
| P1/P2 | Security authority foundations | Partial | Epoch persistence, transition policy, direction-aware administration and the restrictive recovery-bootstrap entry boundary are implemented. RecoveryContext, reconciliation, protected restoration and backup reconstruction remain unimplemented. |
| P1/P2 | Hosted CI evidence | Pending for uncommitted closing tree | Earlier Quality runs verified prior committed baselines; no hosted run is claimed for the current local closing tree. |
| P1 | Interrupted-cycle closure authority | Closed | Exact-attempt closure, runner failure propagation, complete preservation snapshots, restrictive-state coverage, and atomic audit/race tests pass. |
| P1 | Selected mutation/lockdown ordering | Closed for five paths | Task then security SHARE locking covers memory stage/reverse, source creation, general outcome and containment closure; same-task composition and both race orders are proven. Cross-task batching is unsupported. |

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

1. Preserve the closed interruption/ordering guarantees and exact five-path scope.
2. Preserve the closed direction-aware capability policy and its negative matrix.
3. Stop before RecoveryContext, reconciliation, OperatorAuthorization, protected restoration, deployment cloning, backup reconstruction or a generic epoch-replacement API.

### Known implementation question

The closed [bounded decision](cycle-closure-authority.md) uses SECURITY_CONTAINMENT for exact-attempt interruption closure and MEMORY_MUTATION for general outcome writes. Missing/invalid authority or persistence failure propagates through both runners and leaves state unresolved rather than manufacturing closure. Broader recovery and restoration questions remain deferred.

## Navigation

- [Roadmap](roadmap.md) — future and deferred work.
- [Development history](development-history.md) — completed slices and historical evidence.
- [Conformance](conformance.md) — implementation and release-gate rules.
- [Authority matrix](../conformance/authority-matrix.md) — detailed requirement evidence.
- [Implementation status](../conformance/implementation-status.md) — latest verification summary.
- [Security authority](../governance/security-authority.md) — security requirements and historical vocabulary.
- [Repository documentation inventory](../source_of_truth/repository-documentation-inventory.md) — cleanup classification record.
