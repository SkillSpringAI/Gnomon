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
| Full authentication, privileged purge, backup/restore drill, incident response, and complete security-state operationalization | Open release/recovery work |

The conformance records under the current `docs/conformance/` directory provide detailed evidence and limitations until their maintained Markdown destination is established.

## Architectural invariants

The implementation and tests should preserve these invariants:

- The model cannot directly establish authoritative persistent state.
- External agents and retrieved content cannot establish Gnomon policy.
- Accepted substantive knowledge retains provenance.
- Autonomous execution is bounded and has an explicit termination path.
- Provider and adapter failures cannot silently corrupt unrelated authoritative state.
- Conversation context is not authoritative memory.
- Structured state is not replaced solely by semantic similarity.
- Critical mutations are validated before commitment and preserve meaningful audit/history.
- Security and constitutional authority remain outside model reasoning.

When a feature adds a new provider, network, retrieval mechanism, or execution path, it must extend the appropriate boundary and preserve these invariants. It must not make a provider-specific schema, external message, or model output into the system’s authority source.

## Related documentation

- [Documentation map](../README.md)
- [Repository documentation inventory](../source_of_truth/repository-documentation-inventory.md)
- [Current conformance records](../conformance/implementation-status.md)
- [Original architecture authority document](../archive/original-authority-documents/Gnomon%20System%20Architecture%20Authority.docx)
