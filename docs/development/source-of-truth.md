# Gnomon Current Source of Truth

**Last hosted-green implementation baseline:** `ef11f70a53d44bdfa41ad1a4d14d5d523fd27623` (`ef11f70`, uncertain retry and fixture correction). Hosted [Quality run 35937991144](https://github.com/SkillSpringAI/Gnomon/actions/runs/35937991144) tested this exact SHA; `checks`, `minimal-install`, and `browser` all passed.
**Current planning baseline:** `82bab04b6f2972a80c675d0f6b05ddf26ab46897` (`82bab04`, M1.1 RecoveryContext). This exact SHA has local focused verification but no hosted Quality claim yet.
**Previous failure:** Quality run `35818573020` for `11c46ae` failed listing-fixture setup. The corrective commit closes that failure and preserves unconfirmed requests after denied replay.
**Current slice:** Milestone 0 baseline restoration is complete. M1.1 has a committed local [RecoveryContext contract and diagnostic persistence boundary](recovery-context.md), including migration 033, trusted local capture, atomic audit and read validation. M1.2/M1.3 now add local [authorization domain contracts and trusted issuance persistence](authorization.md) for operator grants and epoch-bound execution authorizations, including migration 034, exact replay validation and closeout hardening. M1.4 adds local [read-only recovery reconciliation](recovery-reconciliation.md) over supported evidence and operation streams. M1.5 adds local [protected restoration](recovery-restoration.md), including preflight and audited RECOVERY_REQUIRED fence clearing. M1.6 passes 1-2 add local [authority epoch replacement](authority-epoch-replacement.md) after restoration plus a current execution authorization boundary for protected effects.
**M1.6 review register:** Known authorization gaps to review before M1.6 exit are tracked in [M1 authorization gap register](m1-authorization-pre-m1.6-gap-register.md).
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
- Task-scoped, operator-attributed `derived_from` and `common_origin` relationships with application-appended history, validated history reads, bounded traversal, API adapters, and report/planner/workspace limitation views. Missing relationships remain unknown and never establish independence or increase confidence.
- Evidence-aware next-cycle planning with bounded objectives, persisted planning reasons, reviews, evidence fingerprints, and unresolved work.
- Durable cycle attempts, partial-progress retention, operator recovery, late-write fencing, and explicit blocked/failed outcomes.
- A read-only latest-attempt progress projection and workspace surface for retained evidence, claims, stages, timestamps, objective state, and unresolved active cycles.
- Versioned governed memory for claims and hypothesis assessments with actor context, optimistic concurrency, append-only history, and eligible 48-hour reversal.
- Deterministic snapshots and reports that preserve uncertainty, provenance, cycle outcomes, unresolved objectives, and non-authoritative agent comparison metadata.
- Local rule-based and optional Bedrock provider boundaries with idempotent attempts, bounded output limits, dispatch fencing, and explicit unknown outcomes.
- Local provider-session replacement and deletion are bounded by redacted durable audit, transactional in-memory rollback on stage/commit failure, controlled replacement/delete races, expiry/capacity protections, and populated migration-upgrade evidence. The process-memory crash boundary and authenticated operator identity remain explicit limitations.
- A platform-neutral fake agent network with bounded adversarial scenarios, persisted agent-message evidence, deterministic comparison, and local cycle integration.
- Versioned canonical security state persistence, controlled transitions, and centralized capability policy.
- Point-of-effect enforcement for `READ_AUDIT` on audit/history reads, source retrieval in the cycle runner, and provider dispatch after reservation. Admission alone does not authorize a later effect.
- Authority Epoch persistence and epoch-bound new transition audit records, with fail-closed lineage loading and no runtime epoch creation.
- Post-restoration authority epoch replacement can rotate the singleton epoch,
  bump security-state version, append audit and make old execution authorizations
  fail current-use validation against the new epoch. Exact replay remains
  historical through issuance APIs; `require_current_execution` rejects stale,
  expired, wrong-context or wrong-capability execution authorizations before
  protected effects.
- Explicit transition actor/reason authorization and REDUCE/PRESERVE/BROADEN classification of current capability sets. See [authority foundations](authority-foundations.md) for the matrix and limits.
- Direction-aware `AUTHORITY_ADMINISTRATION`: containment cannot broaden, recovery
  is not a superuser capability, and recovery purpose cannot replace authorization
  for the actual authority-bearing effect.
- Local `OperatorAuthorization` and `ExecutionAuthorization` records are immutable,
  epoch-bound evidence with trusted issuance, audit coupling and exact replay
  checks. They are not consumed for restoration yet and do not replace
  point-of-effect capability checks.
- Startup distinguishes pristine fresh bootstrap, authority-preserving continuation,
  and recovery bootstrap. Recovery entry becomes effectively RECOVERY_REQUIRED before
  requests, keeps restored active-looking records inert, and exposes read-only
  reconciliation plus protected restoration completion.
- Recognized PostgreSQL integrity failures are translated at reviewed write boundaries
  using structured constraint diagnostics; unknown failures remain unexpected, and
  public authority-invariant responses are generic and redacted.
- Operator-controlled stopping decisions use structured reasons, persisted current
  and immutable history records, evidence fingerprints, readiness limitations,
  stale-basis reporting, atomic lifecycle conclusion, and legacy `unspecified`
  compatibility for direct historical conclusions.

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
| Source dependence | Current relationships are explicit, bounded, task-scoped, and auditable; absent or truncated relationships remain unknown. Invalid persisted-graph recovery and causal/semantic independence evaluation remain deferred. |

No current document should claim full autonomous operation, complete security conformance, semantic memory, live agent networking, backup/restore readiness, or v0.1 release conformance.

## Open P0 and P1 work

| Priority | Issue | Current status | Next evidence required |
|---|---|---|---|
| P1 | Backup and restore conformance | Deferred behind authority lineage, transition/restoration authority, bootstrap semantics, and RecoveryContext | Supported PostgreSQL backup/restore procedure, fixture, state/history/provenance/audit comparison, credential non-persistence checks, and release verification. |
| P1/P2 | Historical journal compatibility | Hosted-verified for migration-007 claims/assessments | Populated pre-007 claim/assessment data remains readable through current HEAD without mutation; malformed, missing, and unsupported chains fail closed. Broader memory categories remain deferred. |
| P1/P2 | Workflow atomicity observability | Implementing baseline hosted-verified | Latest-attempt read projection and workspace rendering expose retained progress without observation-side mutation; hosted run `35548463523` passed for exact SHA `41579173fd19e8316d020d4f9c59c624b684fdac`. |
| P1/P2 | Lowest-layer invariant enforcement | Closed locally for reviewed scope | Migration 025 constraints and bounded translation cover reviewed authority/duplicate paths; broader lifecycle and memory vocabulary constraints remain deferred. |
| P1/P2 | Security authority foundations | Partial | Epoch persistence, transition policy, direction-aware administration and restrictive recovery-bootstrap entry are implemented. M1.1 adds a local RecoveryContext domain contract, trusted diagnostic collection/persistence, atomic audit and negative tests. M1.2/M1.3 add local OperatorAuthorization and ExecutionAuthorization domain contracts plus trusted issuance/persistence, atomic audit and replay validation. M1.4 adds read-only recovery reconciliation over supported evidence and operation streams. M1.5 adds protected restoration preflight and audited fence clearing. M1.6 passes 1-2 add post-restoration epoch replacement and current execution authorization validation. Exit-gate evidence and backup reconstruction remain open. |
| P1/P2 | Hosted CI evidence | Milestone 0 closed | Quality run `35937991144` verifies `ef11f70` across all required jobs. The prior failed run remains recorded in the baseline restoration history. |
| P1/P2 | Source-dependence contract | Implementing baseline hosted-verified | Migrations 028/030 provide canonical command replay, history-chain/head validation, bounded lock-stable traversal, invalid examined-graph detection, scoped review invalidation and concurrency coverage. Hosted run 35676307231 verifies 4fa785b. Legacy replay without command metadata, graph repair, database-role separation and privileged tamper resistance remain outside the guarantee. |
| P1/P2 | Trusted-source/provider-session policy audit | Hosted-verified for the reviewed registry and provider-session boundaries | Configuration-scoped events preserve authority epoch/version, require READ_AUDIT to read, and provider-session failure/race/upgrade evidence now covers the reviewed scope; authenticated identity, memory-backend durability, distributed crash atomicity, and unrelated writer audit remain open. |
| P1/P2 | Evidence-bound stopping decisions | Correctness closure hosted-verified | Migrations 029/031/032 persist accepted command identity and cycle-qualified objective references. Authorized exact retries return historical results; derived limitations survive caller caps, history and reports. Readiness retains unfinished objectives, unresolved assessments, current-review uncertainty, contradiction links and incomplete dependence. Runtime limits remain operator-reported. Legacy and pre-final development commands without complete metadata are readable but not replayable. Semantic automatic stopping, authenticated multi-operator identity, and automatic reopening remain deferred. |
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

## Completion-record template

Use this compact record in the relevant maintained status section when a slice closes:

```text
Implementation SHA: <commit tested>
Working tree: <clean or dirty; list relevant uncommitted follow-up>
Commands and results: <exact commands, pass/fail counts, and skips>
Hosted run: <URL, or explicitly pending>
Hosted tested SHA: <SHA, or explicitly pending>
Supported scope: <what the evidence covers>
Remaining gaps: <what is still deferred>
```

Implementation evidence and documentation-only follow-up evidence must remain distinct. A commit must not claim verification of documentation changes that were added after that commit.

## Immediate next work

1. Continue M1.6 pass 3 by refreshing exit-gate evidence and checking remaining stale-epoch consumers.
2. Keep cloning and backup reconstruction outside M1.6 until authority lineage semantics are fully exit-gated.

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
