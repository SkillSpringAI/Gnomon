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

The 26 September documentation baseline reconciled current truth, future work, normative security and transaction vocabulary, INV-01–INV-12, and existing verification evidence while preserving dated records in the archive. Commit `8402fbfbf6dc4fc10f8fd3e94154a61f9db364d6` passed hosted [Quality run 36211693129](https://github.com/SkillSpringAI/Gnomon/actions/runs/36211693129) across all three jobs, with 1,819 passed/28 skipped in the main suite and 28 Chromium browser cases passed separately. The [completion record](c1-documentation-authority-baseline.md) lists every changed file, exact local and hosted results, and environment limits. No runtime or test behavior changed and no C2 implementation began.

## C2 — Recovery shared-read boundary

Closed 27 September 2026 at implementation
`2740d4a8817b01dd3949ae585788512b1a9dbe4b`. Shared recovery basis construction and
supported inventory reads now have recovery-specific internal modules; callers
retain transactions, locks, capability prerequisites, freshness, authorization,
policy and error mapping. [Quality run 36278101826](https://github.com/SkillSpringAI/Gnomon/actions/runs/36278101826)
passed all three required jobs, with 1,848 passed/28 intentional browser skips in
the normal suite and all 28 Chromium cases passed separately with no skips. Both
clean-wheel checks and all 34 migrations passed. The
[closure record](c2-recovery-shared-read-verification.md) distinguishes the tested
implementation commit from subsequent documentation, preserves local verification
and excluded debt, and records that no C3 work began.

## C3a — Continuous reconstruction fencing

Closed 28 September 2026 at implementation
`0618dec6fb6e0eea2942af2ae9ba672234999882`. Reconstruction now persists a
manifest-derived recovery fence and validation-pending gate before PostgreSQL data
import, publishes readiness only after bounded production validation, and then
captures a fresh RecoveryContext. Hosted [Quality run 36367975815](https://github.com/SkillSpringAI/Gnomon/actions/runs/36367975815)
passed all three jobs: 1,886 passed/28 browser-only skips in normal regression,
28 Chromium cases passed separately, and all 35 migrations passed. The real
PostgreSQL reconstruction variants ran hosted with their M2 source/restored
equivalence assertions. The [closure record](c3a-continuous-reconstruction-fence-verification.md)
preserves local limits and the exact hosted evidence. C3a is the final C3 production
implementation slice. A post-C3a architecture review found that private
`_restore_verified_data()` already owns guarded reconstruction and that a separately
constructible C3b component would add callable surface without demonstrated benefit.
C3b extraction was intentionally not implemented; the
[C3 closure rationale](c3a-continuous-reconstruction-fence-verification.md#post-c3a-architecture-review-and-c3-closure)
records the decision and its retained boundaries.

## M3a — Runtime and owner database credentials

Closed 28 September 2026 at implementation
`78a9e408887559e5e100a6f4d22376afee799522`. Hosted
[Quality run 36382958751](https://github.com/SkillSpringAI/Gnomon/actions/runs/36382958751)
passed all three jobs: 1,908 passed/28 browser-only skips in normal regression,
28 Chromium cases passed separately, both real `pg_restore` reconstruction
variants with C3a/M2 equivalence checks, distinct owner/runtime PostgreSQL role
tests, all 35 migrations, and installed-wheel/minimal-install verification. The
[closure record](m3a-runtime-owner-credential-closure.md) distinguishes tested
code-level credential selection from deployment provisioning and retains the
scope of the privilege evidence. M3b had not begun at this M3a closure.

## M3b Pass 2 — Research-cycle status value invariant

Closed 29 September 2026 at implementation
`5038f6f2414c357359e314d2a220932ffcade6bb`. Hosted
[Quality run 36511325666](https://github.com/SkillSpringAI/Gnomon/actions/runs/36511325666)
passed all three jobs: 1,914 passed/28 browser-only skips in normal regression,
28 Chromium cases passed separately, the real invalid-backup reconstruction
rejection and both existing C3a/M2 reconstruction variants, M3a restricted-role
tests, all 36 migrations, and installed-wheel/minimal-install verification. The
[closure record](m3b-cycle-status-constraint-closure.md) preserves the invalid
legacy-row upgrade failure and the scope of the single selected constraint.
Other M3b candidates remain deferred.

## M3c provider-session commit boundary

Closed 29 September 2026 at implementation
`0c55a279dc1664789203794b114e9439f75bf38e`. Hosted
[Quality run 36522924832](https://github.com/SkillSpringAI/Gnomon/actions/runs/36522924832)
passed all three jobs: 1,928 passed/28 browser-only skips in normal regression,
28 Chromium cases, all 36 migrations, and database-wheel/minimal-install
verification. Provider-session tests ran hosted. CREATE now publishes a local
token only after confirmed audit commit; DELETE revokes local capability before
database work and remains fail-closed after failure. The
[closure record](m3c-provider-session-commit-closure.md) retains the exact
failure, concurrency, audit, and synthetic-test limits. Provider-attempt and
external-effect reconciliation were not begun in this slice.

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
