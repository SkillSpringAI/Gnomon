# Gnomon Memory and State Authority

## Purpose and status

This document is the maintained Markdown form of Gnomon’s memory and state authority. It defines how persistent knowledge and authoritative research state are stored, changed, versioned, archived, restored, rolled back, and recovered.

Memory is governed state, not an unstructured transcript. The implementation-status section identifies the current repository’s demonstrated scope; incomplete implementation is a conformance gap, not permission to weaken these rules.

## State categories

Persistent memory must preserve distinctions among information, evidence, claims, entities, relationships, inferences, hypotheses, assessments, conclusions, events, current research state, and historical state. These objects may be connected, but they must not be silently collapsed when doing so would destroy epistemically important information.

| Category | Role |
|---|---|
| Raw evidence | Material acquired from a source or external system. |
| Structured claims | Propositions extracted or generated from evidence. |
| Entities and relationships | Persistent research objects and explicit links among them. |
| Inferences | Derived knowledge generated through reasoning over existing state. |
| Research state | Current task, objective, hypothesis, assessment, cycle, and lifecycle state. |
| Historical state | Prior versions and state transitions retained for audit and recovery. |
| Semantic memory | Derived retrieval representation, never the sole authoritative copy. |

Conversation context is temporary working state. Persistent state must allow a future model instance to reconstruct relevant research context without relying on the original transcript.

## Authoritative state and mutation

Authoritative state is the validated representation of Gnomon’s current state. It is established only through authorized application and domain operations. A model-generated statement or proposal is not authoritative until it passes the appropriate validation path.

Persistent mutations are explicit operations such as create, update, merge, archive, logical delete, restore, retract, and supersede. Each mutation identifies its initiating actor or process separately from the component that authorizes and commits it. The expected flow is:

```text
Proposal
  -> validation
  -> authorization
  -> atomic commit
  -> audit/history
```

Ordinary autonomous operation must not modify authoritative history in place. Corrections create later states or events rather than silently rewriting the original.

## Versioning, identity, and concurrency

Important mutable state is versioned or otherwise historically recoverable. State-changing events should have immutable identities and retain event type, actor, timestamp, affected object, previous and resulting versions, reason, task, and correlation or operation identity where applicable.

State-changing operations should be idempotent where practical. Critical transitions use compare-and-set or equivalent version checks so an old process cannot silently overwrite newer state. Concurrent changes must be serialized, merged, explicitly rejected, or raised as a conflict; processing order alone is not a valid resolution.

### Legacy governed-memory compatibility

Migration 007 added version-one and lifecycle fields to existing claims and
hypothesis assessments without an original journal row. The supported upgrade
shape is therefore a first retained journal mutation with
`previous_version=1`, `version=2`, and a non-null `previous_state`. That state
is a supported version-one reconstruction baseline for claims and assessments,
but it does not establish the original creation event, actor, timestamp, or
change identity. The API reports no synthetic change ID for that baseline.

Newly governed targets continue to require a version-one `CREATE` journal row.
A target with no journal is not reconstructable and is reported as missing
history. Missing intermediate versions, mismatched previous state, malformed
state, invalid target types, and unsupported starting shapes are rejected as
conflicts. Historical reads validate the chain and state shapes without
writing records, changing current state, or fabricating history. This contract
covers claims and hypothesis assessments only; it is not backup restoration or
disaster recovery.

## Provenance dependencies

Important dependencies should be representable as a directed provenance graph. Typical relationships include `DERIVED_FROM`, `SUPPORTS`, `CONTRADICTS`, `INFERRED_FROM`, `SUPERSEDES`, `REPORTED_BY`, `CORROBORATES`, and `DEPENDS_ON`.

Dependency information supports retraction, rollback, reassessment, pruning, contradiction propagation, and research reproducibility. A change to one item must not silently leave dependent claims, inferences, or conclusions presented as unaffected.

Rollback operates on provenance and dependency relationships rather than on text matching or indiscriminate deletion. Independent evidence survives a rollback of one contributing source or agent. Dependent knowledge may be retracted, marked for reassessment, recomputed, or retained when an independent valid path remains.

## Reversible state and rollback

Rollback restores relevant valid current state without destroying the historical record of the attempted change. The history remains distinguishable as:

```text
State A -> Mutation B -> Rollback C
```

The initial target is a 48-hour reversible window for applicable autonomous memory mutations. A mutation is eligible only when it is within the configured window, prior state remains available, no immutable constraint prevents reversal, and the inverse operation will not silently destroy subsequent legitimate changes.

Rollback must be auditable and idempotent. If it would overwrite a newer legitimate change, the system must reject it, create a conflict, perform a dependency-aware inverse operation, or request authorized resolution. Rollback is not historical erasure.

## Lifecycle, archive, deletion, and retention

The canonical lifecycle is explicit, though not every object uses every state:

```text
PROPOSED -> VALIDATED -> ACTIVE -> UPDATED
                         |          |
                         v          v
                      ARCHIVED <- RESTORED
                         |
                         v
                 LOGICALLY_DELETED
                         |
                         v
                   PURGE_ELIGIBLE
                         |
                         v
                PERMANENTLY_PURGED
```

Archiving removes an item from ordinary active retrieval while retaining it. Restoration preserves the original inactive event and adds a restoration event. Ordinary autonomous deletion should be logical deletion, not physical destruction.

Permanent purge is privileged, explicitly authorized, subject to retention policy, auditable, and outside ordinary model capabilities. Retention policies may vary by data class, but must not silently undermine provenance, auditability, active research, unresolved claims, rollback, or required historical conclusions.

Pruning is allowed for redundant data, obsolete intermediates, low-value retrieval artifacts, expired temporary state, and duplicate derived memories. Text similarity alone does not prove redundancy: similar records may represent independent sources, different contexts, different populations, or contradiction.

## State integrity and atomicity

Persisted objects must not enter impossible states, including accepted claims without required provenance, restored objects with missing history, versions that reference nonexistent predecessors, conclusions that depend on permanently removed required state, or events for mutations that never committed.

Where multiple records form one logical mutation, they should commit atomically. A claim, provenance link, evidence relationship, and audit event should normally succeed or fail as one operation. If atomicity is not possible, the intermediate state must be explicit and recovery deterministic; it must not be reported as a successful completion.

## Access, derived state, and exports

Model access to memory occurs through controlled retrieval services rather than unrestricted database access. Retrieved context preserves source, claim, inference, hypothesis, uncertainty, and provenance distinctions.

Search indexes, embeddings, caches, and summaries are derived artifacts that can be rebuilt from authoritative state. Their loss or corruption must not constitute loss of authoritative research knowledge. Exports and external disclosures preserve provenance and epistemic status and must not transform an unverified claim into a fact by omitting uncertainty.

Constitutional and security policy state is separate from ordinary research memory. Ordinary memory operations cannot mutate those authorities. Memory-derived external communication must evaluate disclosure permission, sensitivity, provenance, uncertainty, and recipient authorization.

## Mandatory memory invariants

1. Authoritative state changes only through authorized application or domain operations.
2. Model proposals are not authoritative state.
3. Important mutable state is versioned or historically recoverable.
4. Historical state is not silently rewritten.
5. Accepted substantive knowledge retains provenance.
6. Important dependencies are representable.
7. Applicable autonomous memory mutations are reversible within the defined 48-hour window.
8. Logical deletion precedes permanent destruction for ordinary autonomous operations.
9. Permanent purge is not an ordinary model capability.
10. Rollback cannot silently overwrite newer incompatible state.
11. Derived indexes and embeddings are not the sole authoritative copy.
12. Contradictory knowledge can coexist.
13. Semantic similarity alone cannot justify destructive merging.
14. Pruning cannot silently destroy required provenance or active dependencies.
15. Rollback remains distinguishable from historical erasure.

## Memory integrity test

For any significant mutation, Gnomon should be able to answer:

- What object changed, and what were its previous and resulting states?
- Who or what proposed and authorized the change?
- Why did it occur, and what evidence or input motivated it?
- What provenance and dependent objects are affected?
- Is the mutation reversible, until when, and under what conditions?
- What happens if a newer change conflicts with rollback?
- What audit record proves the transition occurred?

## Current implementation status

| Requirement area | Current evidence and limitation |
|---|---|
| Governed proposal, validation, commit, actor context, and audit | Implemented for claims and hypothesis assessments, with deterministic validation and redacted audit metadata. |
| Versioned state and append-only history | Implemented for governed claims and assessments with optimistic versions and a change journal, including the bounded migration-007 version-one baseline rule; not every planned memory category exists yet. |
| 48-hour rollback | Implemented for eligible claim and assessment changes with stale, duplicate, concurrent, dependent, expired, and conflict checks. |
| Lifecycle and task state integrity | Implemented for current investigation, cycle, provider-attempt, and memory paths; broader purge and retention policy remain open. |
| Provenance and dependencies | Current sources, claims, assessments, cycle associations, and agent observations retain provenance; full dependency-aware propagation and graph reconstruction remain partial. |
| Contradictory and superseded knowledge | Current reports and assessments preserve uncertainty and contradiction metadata; comprehensive supersession/retraction propagation is not complete. |
| Rebuildable derived state and semantic memory | Structured persistence is authoritative; vector/semantic memory and broad rebuildable indexes are deferred. |
| Access control, export review, backup, and restoration | Current local/operator boundaries, audit redaction, and the bounded M2 reconstruction/recovery drill exist; full authentication, a consolidated operator procedure, broader deployment evidence, and privileged purge controls remain release work. |

The [architecture overview](../architecture/overview.md), [epistemic authority](epistemic-authority.md), [constitutional principles](constitutional-principles.md), and [conformance records](../conformance/implementation-status.md) provide supporting evidence and limitations.

## Related documentation

- [Documentation map](../README.md)
- [Architecture overview](../architecture/overview.md)
- [Epistemic authority](epistemic-authority.md)
- [Constitutional principles](constitutional-principles.md)
- [Repository documentation inventory](../source_of_truth/repository-documentation-inventory.md)
- [Original authority document retained during cleanup](../archive/original-authority-documents/Gnomon%20Memory%20%26%20State%20Authority.docx)
