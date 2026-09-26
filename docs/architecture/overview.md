# Gnomon Architecture Overview

## Purpose

Gnomon is a local-first research API whose authoritative state is persisted outside model conversation context. Its architecture separates reasoning, external capabilities, deterministic validation, persistence, and infrastructure so that more capable models do not receive more authority over the system.

This overview is the maintained implementation-facing summary of the architectural authority material. It describes the current repository and labels future or partial capabilities explicitly. The source authority document remains in `docs/` until the authority-document conversion and archive pass is complete.

## Current implementation shape

```text
Client
  |
  v
API / CLI
  |
  v
Application services
  |-- investigations and lifecycle
  |-- evidence, claims, and provenance
  |-- cycle planning and bounded execution
  |-- memory governance and rollback
  |-- reports and provider drafts
  |-- audit and security state
  |
  +--> Domain objects and validation
  +--> Ports
          |-- LLM providers
          |-- web retrieval
          |-- agent network
          |-- reporting and repositories
  |
  v
Persistence and migrations
  |
  v
PostgreSQL (reference durable store)
```

The corresponding package boundaries are `api`, `application`, `domain`, `ports`, `adapters`, `persistence`, `config`, and `security` under `src/research_agent/`. The current implementation favors incremental extension of these boundaries rather than replacing them with a new orchestration layer.

## Architectural boundaries

### Interface layer

FastAPI routes and the CLI validate and serialize requests. They delegate domain behavior to application services and do not define epistemic authority.

### Application layer

Application services coordinate use cases such as investigation lifecycle, evidence collection, claim extraction, hypothesis assessment, cycle planning, report assembly, provider drafts, memory proposals, audit events, and security-state transitions. They own orchestration and transaction boundaries while relying on domain validation and persistence ports.

### Domain layer

Domain models represent investigations, cycles, hypotheses, sources, evidence, claims, assessments, agents, observations, reports, events, and security state. Domain code is not coupled to PostgreSQL, AWS, a specific model SDK, or a network platform.

### Ports and adapters

Ports define replaceable capabilities. Adapters currently include HTTP retrieval, deterministic rule-based providers, optional Bedrock providers, and a bounded fake agent network. Live external-agent platform adapters, semantic/vector retrieval, and broad tool registries remain future work.

### Persistence and infrastructure

PostgreSQL is the reference persistence implementation. SQL migrations define schema evolution and checksum protections. Application services keep domain rules above storage and use transactions, row locks, compare-and-set transitions, optimistic versions, or operation identities where required by the operation.

## Authority and data flow

External material enters as untrusted data. It is stored with retrieval metadata and provenance, then processed by deterministic services. Claims and governed memory changes are proposals until application and domain validation accepts them. Accepted state changes are persisted with the required provenance and audit information.

The model or provider may propose reasoning, plans, claims, or report prose. It cannot directly write authoritative state, change policy, grant itself capabilities, or execute arbitrary infrastructure commands. External agents and retrieved content have no authority to redefine Gnomon policy.

## Current research cycle flow

1. An API or CLI request creates or loads an investigation.
2. The application validates the lifecycle state and determines permitted work.
3. Deterministic planning selects a bounded set of objectives from persisted evidence and assessments.
4. An approved runner acquires source or fake-agent observations through an adapter.
5. Evidence, claims, provenance, progress, and cycle outcomes are persisted through application services.
6. Reports expose structured state, uncertainty, unresolved objectives, and non-authoritative comparison metadata.
7. The operator may review outcomes, resume or pause work, recover interrupted execution, or request a bounded provider draft.

Every bounded execution path has an explicit completed, blocked, failed, or recovery outcome. Provider attempts use durable operation identities and preserve capacity for dispatched or uncertain work until explicitly reconciled.

## What is implemented and what is not

| Architectural capability | Current status |
|---|---|
| Layered API, application, domain, ports, adapters, and persistence boundaries | Implemented in the current package structure |
| PostgreSQL-backed investigations, evidence, claims, assessments, cycles, reports, audit, and security state | Implemented and covered by unit/integration tests |
| Deterministic planning, bounded local cycle execution, and interrupted-cycle recovery | Implemented for the current local scope |
| Governed memory proposals, versioning, append-only change history, and eligible rollback | Implemented for claims and hypothesis assessments; broader dependent-state propagation remains open |
| Provider-neutral LLM boundary and optional Bedrock adapter | Implemented; provider behavior is bounded and audited with redacted metadata |
| HTTP boundary controls and untrusted-content delimiting | Implemented for the current HTTP and provider paths; broader adapter coverage remains open |
| Fake agent network and persisted agent observations | Implemented as a bounded read-only contract and local cycle path |
| Live external-agent network, Moltbook adapter, long-running orchestration, and deployment queues | Not implemented |
| Semantic/vector memory, object-storage source model, entity canonicalization, and cross-task retrieval | Deferred or partial |
| Full authentication, privileged purge, incident response, and complete security-state operationalization | Open release/recovery work; the bounded M2 backup/reconstruction/recovery drill is hosted-verified, while a consolidated operator procedure and broader deployment evidence remain open |

The conformance records under the current `docs/conformance/` directory provide detailed evidence and limitations until their maintained Markdown destination is established.

## Architectural invariants

This register states durable architectural rules. It does not assert that every rule has complete executable coverage; the [architectural invariant verification map](../conformance/architectural-invariant-verification.md) identifies supported evidence, documented rules, and remaining gaps.

| ID | Invariant |
|---|---|
| INV-01 | Governed mutation fails closed: missing, stale, contradictory, or unauthorized authority never silently grants permission. |
| INV-02 | Consequential external dispatch requires its durable attempt or reservation state to commit before dispatch. |
| INV-03 | Governed database locks and transactions are released before slow, untrusted, or external work. Validate and persist authority, commit, perform external work, then reacquire and revalidate before governed mutation. |
| INV-04 | Governed state and its required audit or history evidence commit atomically; audit failure rolls back the mutation. |
| INV-05 | Runner write authority is bound to its exact durable execution attempt. A terminally closed attempt cannot regain authority because the investigation later becomes active. |
| INV-06 | Operator execution recovery is bound to the observed progress fingerprint; a stale fingerprint fails. |
| INV-07 | Authorized trusted mechanisms may restrict authority. Recovery-qualified state transitions require their separate actor, reason, and capability checks; a pending recovery-bootstrap fence blocks those transitions and requires the dedicated protected restoration path before ordinary authority returns. |
| INV-08 | SecurityState, recovery bootstrap state, AuthorityEpoch, execution attempt identity, and recovery fingerprint remain separate authority dimensions. |
| INV-09 | Governed audit, review, authority, and historical evidence remains append-only wherever its contract specifies append-only history. |
| INV-10 | Source, provider, and agent execution retain explicit orchestration. They may share bounded lifecycle vocabulary and narrow primitives without requiring a generic runner or workflow engine. |
| INV-11 | A persistence abstraction must state any stronger concrete infrastructure it needs for an advertised operation. Durable execution dependencies are explicit at composition boundaries. |
| INV-12 | Successful database reconstruction does not establish ordinary operational trust. Reconstructed state passes through governed recovery before ordinary authority is restored. |

These rules complement the existing model, evidence, and runtime boundaries: model output, external agents, and retrieved content cannot establish Gnomon policy or directly write authoritative state; accepted substantive knowledge retains provenance; conversation context and semantic similarity do not replace structured authoritative memory; autonomous execution remains bounded with an explicit termination path. New execution or adapter paths must preserve these boundaries.

## Related documentation

- [Documentation map](../README.md)
- [Repository documentation inventory](../source_of_truth/repository-documentation-inventory.md)
- [Current conformance records](../conformance/implementation-status.md)
- [Architectural invariant verification map](../conformance/architectural-invariant-verification.md)
- [Original architecture authority document](../archive/original-authority-documents/Gnomon%20System%20Architecture%20Authority.docx)
