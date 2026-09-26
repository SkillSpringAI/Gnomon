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

Completed 15 September 2026 for the reviewed scope. Security state gained canonical persisted records, versioned transitions, compare-and-set controls, centralized capability policy, operator visibility, bounded API enforcement, transition tests, and an exit-gate hardening pass. At that checkpoint the older authority-document vocabulary still required reconciliation with the Slice 13 model. The maintained [security authority](../governance/security-authority.md#security-state-and-containment) now records the reconciled current vocabulary; this dated note remains as provenance.

## Verification baseline

The 15 September baseline recorded 296 passed and 5 skipped tests for the reviewed local suite, with Ruff and strict mypy passing, all 20 packaged migrations applying to a fresh database and rerunning idempotently, clean-wheel verification passing outside the checkout, smoke and real-HTTP checks passing, and authority traceability checks passing. These results establish a regression baseline, not full conformance or release readiness.

No hosted CI result, live Bedrock call, live external-agent call, deployment penetration test, or backup/restore drill was claimed at that baseline.

## Milestone 0 — Hosted baseline restoration

The 24 September fixture and browser-retry correction at `ef11f70` restored a green canonical baseline after the failed `11c46ae` Quality run. Hosted [Quality run 35937991144](https://github.com/SkillSpringAI/Gnomon/actions/runs/35937991144) passed the required jobs for the corrective SHA. The [closure record](../archive/completed-slices/2026-09-24-baseline-restoration.md) retains the failed run, exact local and hosted results, and supported scope.

## Milestone 1 — Recovery authority

M1.1–M1.6 established a bounded local recovery context, separately issued operator and execution authorization, deterministic read-only reconciliation, protected restoration, and authority epoch replacement. Hosted [Quality run 35981852013](https://github.com/SkillSpringAI/Gnomon/actions/runs/35981852013) passed at `316c90bf1816743ce73571e907b5c24e4da6cdec`. The [M1.6 evidence map](authority-epoch-replacement.md#exit-gate-evidence-map) and linked M1 records retain adversarial tests and limits; M2 reconstruction and broader deployment recovery were outside that M1 claim.

## Milestone 2 — Backup and reconstruction sequence

M2.1–M2.11 established the supported PostgreSQL backup and guarded reconstruction path, canonical baseline and restrictive-fixture equivalence, recovery-bootstrap entry, fresh reconciliation and authorization, protected restoration with atomic epoch rotation, and credential-sentinel verification. The final implementation checkpoint `93e383eb0acf8ba2a389d888c45023355b0ff7af` passed hosted [Quality run 36108631071](https://github.com/SkillSpringAI/Gnomon/actions/runs/36108631071) across `checks`, `minimal-install`, and `browser`; the main suite reported 1,819 passed and 28 skipped. This is the bounded functional M2 baseline, not a general release-conformance claim.

The [completed incremental sequence](M2%20Incremental%20Implementation%20Sequence.md) and its linked M2.1–M2.11 records retain the per-slice implementation, failure, verification, and hosted-run evidence. The maintained [roadmap](roadmap.md#milestone-2-backup-restore-and-reconstruction-conformance) owns the remaining architectural consolidation.

## C1 — Documentation authority and invariant baseline

The 26 September documentation baseline reconciled current truth, future work, normative security and transaction vocabulary, INV-01–INV-12, and existing verification evidence while preserving dated records in the archive. The [completion record](c1-documentation-authority-baseline.md) lists every changed file, exact local results, environment limits, and pending commit/hosted gates. No runtime or test behavior changed and no C2 implementation began.

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
- [Pre-C1 current-state journal](../archive/completed-slices/2026-09-26-pre-c1-source-of-truth-journal.md) — retains the M2.7 closeout record and dated status language.
- [Pre-C1 implementation-status journal](../archive/completed-slices/2026-09-26-pre-c1-implementation-status-journal.md) — retains historical commands, failures, and checkpoint limits.
- [Pre-C1 detailed roadmap](../archive/superseded-plans/2026-09-26-pre-c1-roadmap-detail.md) — retains completed M0/M1 instructions and exit-gate narrative.
