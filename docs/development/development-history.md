# Gnomon Development History

## Purpose

This document preserves meaningful completed work and exit-gate evidence without presenting historical plans as current requirements. Dated reviews and original source documents remain recoverable in `docs/source_of_truth/`, `docs/conformance/`, and the archive after the cleanup is complete.

## Foundation and early implementation

The repository established a local-first Python research API with PostgreSQL, Docker Compose, FastAPI, a CLI, migrations, unit/integration testing, linting, typing, smoke checks, and a layered package structure. Early slices introduced investigations, briefs, hypotheses, questions, sources, claims, provenance, assessments, lifecycle state, and bounded planning.

## Slices 1–9

The initial implementation sequence added, in order, the repository/authority baseline, structured investigation planning, source retrieval and evidence storage, claims and provenance, snapshots and reports, memory governance foundations, bounded agent-network contracts, and local cycle integration. The resulting implementation remains deliberately smaller than the full authority model: live external networks, semantic memory, distributed workers, and broad autonomous orchestration were not completed in these slices.

## Slice 10A — Historical authority hardening

Completed 14 September 2026. Governed claim and assessment history became explicit and reconstructable through target/version retrieval, journal validation, reversal history, and replacement of authority-sensitive assertions with explicit failures. The remaining compatibility question concerns future or older journal formats.

## Slice 10B — Persistence invariant hardening

Completed 14–15 September 2026. Migration 012 added journal and operation checks, migration tracking gained SHA-256 checksums and drift rejection, migration 014 added governed archive state, direct SQL tests covered invalid journal writes and retained-audit deletion, and CI was repaired to run the required quality and integration gates. No production physical-purge operation was introduced.

## Slice 11 — Persistent execution attempts and crash recovery

Completed before the Slice 12 hardening baseline. Cycle and provider execution gained durable attempt identities, persisted progress, partial-result retention, operator recovery, late-write fencing, explicit blocked/failed outcomes, and tests for interruption and recovery. Future live networks require their own recovery evidence.

## Slice 12A — Provider budget and concurrency governance

Completed 15 September 2026. Provider attempts gained persistent reservations, operation IDs, atomic capacity authorization, dispatch fencing, explicit `PENDING`, `DISPATCHED`, `UNKNOWN`, `SUCCEEDED`, `FAILED`, and `EXPIRED` states, idempotent finalization, controlled recovery, and concurrency/interleaving tests. Unknown dispatched work retains capacity; automatic timeout refunds and retries are not assumed.

## Slice 12B — Installation, configuration, and public-audit contracts

Completed 15 September 2026. Clean-wheel resources, concurrent bootstrap, populated upgrades, migration drift rejection, configured memory lifetime, provider settings and limits, public reason categories, session-provider token limits, unknown-task rejection, and redacted public audit behavior were verified. The working changes were locally verified; hosted CI confirmation remained pending at the cleanup baseline.

## Slice 13 — Security state machine

Completed 15 September 2026 for the reviewed scope. Security state gained canonical persisted records, versioned transitions, compare-and-set controls, centralized capability policy, operator visibility, bounded API enforcement, transition tests, and an exit-gate hardening pass. The authority-document vocabulary still requires reconciliation with the Slice 13 model before the security state can be considered fully canonical.

## Verification baseline

The 15 September baseline recorded 296 passed and 5 skipped tests for the reviewed local suite, with Ruff and strict mypy passing, all 20 packaged migrations applying to a fresh database and rerunning idempotently, clean-wheel verification passing outside the checkout, smoke and real-HTTP checks passing, and authority traceability checks passing. These results establish a regression baseline, not full conformance or release readiness.

No hosted CI result, live Bedrock call, live external-agent call, deployment penetration test, or backup/restore drill was claimed at that baseline.

## Historical decisions retained

- Preserve adapters → ports → application → governance/security → persistence boundaries.
- Do not rush live agent networking before authority, persistence, and recovery guarantees mature.
- Treat the memory journal as the candidate canonical historical authority rather than creating competing histories.
- Preserve committed intermediate evidence across later cycle failure.
- Prefer archive and logical lifecycle operations over ordinary physical deletion.

These decisions remain useful context but are subordinate to the current source of truth, maintained authority documents, implementation evidence, and the roadmap.

## Historical source records

- [Original source-of-truth working document](../archive/superseded-plans/GNOMON_SOURCE_OF_TRUTH.md)
- [Architecture and deep code review](../archive/completed-slices/Gnomon-Architecture-Code-Review-2026-09-15.md)
- [Next-two-slices review](../archive/superseded-plans/Gnomon-Next-Two-Slices-2026-09-15.md)
- [Slice 13 security state model](../source_of_truth/Slice%2013%20Security%20State%20Model%20and%20Transition%20Table.md)
- [Implementation status](../conformance/implementation-status.md)
