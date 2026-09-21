# Gnomon Persistence and Data Authority

## Purpose and status

This document is the maintained Markdown form of Gnomon’s persistence and data authority. It defines canonical state, data classes, provenance, history, transactions, migrations, concurrency, recovery, retention, and the boundary between authoritative and derived storage.

The current reference implementation is a local-first PostgreSQL-backed API with versioned SQL migrations and application-level persistence services. The implementation-status section identifies the current scope and open work.

## Governing data principles

1. Canonical state has an explicit authority.
2. Persistence is not truth by itself.
3. Provenance persists with substantive knowledge.
4. Historical state matters.
5. Derived state is rebuildable.
6. Relationships are first-class.
7. Deletion is governed.
8. Storage boundaries do not change epistemic meaning.
9. Data integrity is a system property.
10. Recovery is designed into persistence.

The database stores validated system state; it does not independently define Gnomon’s research semantics. Domain and application rules, database constraints, transactions, audit history, and tests provide complementary integrity defenses.

## Canonical data classes

Persistence preserves distinctions among:

| Class | Meaning |
|---|---|
| Raw source data | Material obtained from a source or external system. |
| Observations | What was encountered or recorded, including agent observations. |
| Claims | Propositions that can be evaluated against evidence. |
| Entities and relationships | Research objects and explicit typed links. |
| Inferences | Derived propositions with dependencies on inputs. |
| Hypotheses and assessments | Propositions under investigation and current evidence evaluations. |
| Conclusions | Traceable research syntheses, not source records. |
| Memory | Governed reusable state with lifecycle and history. |
| Research state | Current task, cycle, objective, lifecycle, and execution state. |
| Events | Structured history of mutations, outcomes, audit, and recovery. |

Storage format must not collapse these classes into generic text when doing so would erase epistemic status, provenance, uncertainty, or dependency meaning.

## Persistence authority and boundaries

Authoritative state is established through application and domain operations. Model output, external-agent messages, reports, caches, embeddings, and raw storage artifacts are not authoritative merely because they are persisted.

Data access occurs through controlled repositories and services. The model does not receive unrestricted database access. Reports and summaries are derived views of persisted state and must not create a new epistemic reality.

The current package boundaries are under `src/research_agent/persistence/`, `src/research_agent/application/`, `src/research_agent/domain/`, and `src/research_agent/migrations/`. PostgreSQL is the reference durable store; providers, web retrieval, agents, and derived indexes remain replaceable boundaries.

## Provenance, identity, and integrity

Every accepted substantive claim and agent-derived contribution retains provenance sufficient to identify source, task, operation, actor or initiating process, timestamps, transformations, and supporting or contradicting relationships where applicable.

Source identity should use stable identifiers, retrieval metadata, content hashes, versions, and origin information. Deduplication must not equate similar text with identical knowledge: records may represent independent sources, different contexts, populations, periods, or contradictions.

Content addressing and integrity checks may detect changes, but a hash does not establish truth. Source reliability, claim confidence, and persistence integrity remain separate properties.

## State mutation and history

Persistent changes are explicit operations such as create, update, merge, archive, logical delete, restore, retract, supersede, rollback, and recovery. Important mutable state is versioned or historically recoverable. Historical records and events are not silently rewritten; corrections and reversals create subsequent state or events.

Mutation records should preserve operation identity, actor, reason, prior and resulting state or versions, affected relationships, task/cycle scope, timestamps, provenance, and audit outcome. Reports do not replace this history.

Governed claims and hypothesis assessments upgraded by migration 007 may have a
version-one current record without an original journal row. Their first
governed mutation is reconstructable only when it retains a valid version-one
`previous_state` and records the mutation as version two. The baseline is
historical state, not an invented creation event: its actor, timestamp, and
change identity remain unknown. New targets still require a version-one create
row; gaps, mismatched states, malformed payloads, and unsupported starting
shapes fail closed. History and version reads are side-effect free.

## Transactions and concurrency

Related state changes commit atomically where practical. For example, a claim, required provenance, evidence relationships, and audit record should succeed or fail as one logical operation. If a multi-step operation cannot be atomic, intermediate or unknown state is explicit and recoverable; it is not reported as successful completion.

Concurrency controls prevent silent overwrite. Depending on the operation, the implementation uses transactions, row locks, compare-and-set lifecycle transitions, optimistic versions, unique operation identities, and idempotency. An old process cannot silently replace newer legitimate state.

External operations have explicit outcomes. A provider or network call that may have executed but whose result is unknown remains unknown until reconciled; it is not blindly retried or refunded as if no side effect occurred.

## Research and execution state

Persistence retains task lifecycle, cycle planning and progress, objectives, evidence associations, claims, assessments, reports, provider attempts, agent observations, audit events, and security state within their respective authority boundaries.

Research workflow state is separate from epistemic state. An investigation can be paused, concluded, or failed while its claims remain uncertain, contested, or unresolved. Cycle outcomes retain meaningful progress, unresolved objectives, provenance identifiers, and recovery metadata.

## Derived state and rebuildability

Search indexes, embeddings, caches, summaries, and report projections are derived artifacts. They should be rebuildable from authoritative structured state. Loss or corruption of a derived index must not equal loss of research knowledge.

Semantic retrieval may discover candidate material but cannot replace structured claims, provenance, event history, or authoritative state. Raw object storage may hold large source material in a future deployment, but its use must not change epistemic semantics.

## Lifecycle, retention, and deletion

Lifecycle is explicit: proposed, validated, active, updated, archived, logically deleted, restored, purge-eligible, and permanently purged as applicable to the object. Archive and logical delete preserve recoverable history. Permanent purge is privileged, explicitly authorized, retention-aware, and outside ordinary model authority.

Retention classes may differ for temporary retrieval artifacts, evidence, audit history, rollback state, and constitutional/security history. Pruning must preserve provenance, active research, unresolved claims, rollback eligibility, auditability, and historical conclusions required by policy.

## Schema evolution and migrations

Schema changes are versioned migrations. Migration application is ordered, checksummed, idempotent, and verified against a fresh database and populated upgrade path. Migration drift must be rejected rather than silently accepted.

The current migration implementation resides under `src/research_agent/migrations/`; [migration operations](../../migrations/README.md) remain in the repository root during cleanup. Migrations are database schema history, not a substitute for governed memory rollback. Downgrade support remains a separate capability and is not implied by rollback of research state.

## Backup, recovery, and repair

Backups preserve authoritative state, provenance, event history, and migration compatibility. Backup verification and restoration must demonstrate that state can be recovered without silently erasing history or altering epistemic meaning.

Recovery follows a hierarchy of durable state, committed operations, explicit unknown outcomes, audit/history, verified backup, and authorized repair. Repair is controlled and attributable; it must not silently rewrite evidence or manufacture a successful outcome.

The current repository has transactional recovery, cycle recovery, provider-attempt reconciliation, migration verification, and governed rollback tests. A complete operational backup/restore procedure and restore drill remain open release work.

## Security and portability

Persistence access is subject to authorization, task scope, data minimization, and privacy controls. Exports and imports preserve identifiers, provenance, epistemic status, uncertainty, and history where required. Storage-provider or deployment changes must not turn an unverified claim into a fact, remove provenance, or weaken lifecycle semantics.

## Mandatory persistence invariants

1. Canonical state has an explicit authority.
2. Persistence is not truth.
3. Provenance persists.
4. Historical integrity is preserved.
5. Mutations are explicit.
6. Related changes are transactionally consistent.
7. Concurrent changes cannot silently corrupt state.
8. Repeated operations are idempotent where required.
9. Unknown outcomes remain explicit.
10. Relationships and dependencies remain intact.
11. Contradictory knowledge can coexist.
12. Derived state is not authoritative by itself.
13. Derived indexes and caches are rebuildable.
14. Logical deletion precedes ordinary permanent destruction.
15. Permanent purge is privileged.
16. Recovery is designed and tested.
17. Provenance is preserved through storage and migration.
18. Dependency-aware reassessment remains possible.
19. Epistemic distinctions survive persistence.
20. Semantics remain portable across storage implementations.

## Persistence integrity test

For any significant persisted mutation, Gnomon should be able to answer:

- What authoritative object changed?
- What was its prior state and version?
- What operation and actor initiated and authorized it?
- What provenance, relationships, and dependent records are affected?
- Which transaction, event, or operation identity proves the transition?
- What happens on duplicate delivery, concurrent change, partial failure, or unknown external outcome?
- Can current and historical state be reconstructed?
- Can derived state be rebuilt from authoritative records?

## Current implementation status

| Requirement area | Current evidence and limitation |
|---|---|
| PostgreSQL canonical persistence and migration chain | Implemented with 22 ordered migrations, checksum/drift protections, fresh-database application, and idempotent reruns. |
| Investigations, evidence, claims, assessments, cycles, reports, audit, and security state | Implemented in current persistence and application services with integration coverage. |
| Transactions and concurrency | Implemented with task-row locks, transactions, optimistic versions, compare-and-set lifecycle operations, and atomic audit/error handling for reviewed paths. |
| Idempotency and unknown outcomes | Implemented for provider attempts, cycle recovery, lifecycle finalization, and governed memory operations within current scope. |
| Provenance and historical state | Implemented for current sources, claims, assessments, cycles, agent observations, and governed memory history; full dependency graph reconstruction remains partial. |
| Derived state and semantic indexes | Structured state remains authoritative; broad vector/search index rebuildability and object-storage source separation are deferred. |
| Deletion, purge, retention, backup, and restore | Logical/archive protections and tests exist; privileged purge policy and operational backup/restore drill remain open. |
| Distributed storage and portability | Not implemented; local PostgreSQL is the current reference deployment. |

The [architecture overview](overview.md), [memory authority](../governance/memory-authority.md), [security authority](../governance/security-authority.md), [workspace verification](../operations/workspace-verification.md), and [conformance records](../conformance/implementation-status.md) provide supporting evidence and limitations.

## Related documentation

- [Documentation map](../README.md)
- [Architecture overview](overview.md)
- [Memory authority](../governance/memory-authority.md)
- [Security authority](../governance/security-authority.md)
- [Epistemic authority](../governance/epistemic-authority.md)
- [Repository documentation inventory](../source_of_truth/repository-documentation-inventory.md)
- [Migration operations](../../migrations/README.md)
- [Original authority document retained during cleanup](../archive/original-authority-documents/Gnomon%20%E2%80%94%20Persistence%20%26%20Data%20Authority.docx)
