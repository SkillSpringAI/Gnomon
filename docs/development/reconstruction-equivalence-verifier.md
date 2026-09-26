# Reconstruction Equivalence Verifier — M2.7

> Dated execution and verification record. Status and remaining-work statements below describe this checkpoint; use the maintained [current source of truth](source-of-truth.md) and [roadmap](roadmap.md) for present claims.

Date: 25 September 2026.
Status: canonical backup/restore equivalence hosted-verified at `a75e47a`.

## Scope

M2.7 adds `tests/integration/m2_reconstruction_equivalence.py`.

The helper builds deterministic comparison projections for:

- research;
- evidence and provenance;
- assessments;
- source dependence;
- memory;
- stopping decisions;
- execution attempts;
- provider attempts;
- audit;
- security state and Authority Epoch;
- recovery and authorization;
- migration state.

It also compares deterministic `SnapshotService` and `ReportService`
projections for the canonical fixture task.

## Boundary

The verifier is intentionally projection-based. It avoids whole-database dumps
and unordered row comparison. Each group uses explicit stable ordering and is
intended to support later backup -> restore equivalence drills.

The real PostgreSQL integration test now performs backup, restore and full
projection comparison for both the baseline and restrictive/unresolved fixture
variants. The `security_state.updated_at` field is excluded from comparison:
reconstruction writes a new update timestamp when it applies the manifest's
authority state. State, version, epoch, bootstrap flag and transition history
remain in the comparison. Credential sentinel scan, recovery bootstrap and
epoch rotation remain separate work.

## Verification

Local M2.7 verification:

- `python -m pytest tests/integration/test_m2_reconstruction_fixture.py tests/integration/test_m2_reconstruction_equivalence.py` — 4 passed.
- Combined M2.1-M2.7 suite — 59 passed, 2 skipped because `pg_dump` and `pg_restore` are unavailable in the local environment.
- Ruff — passed.
- Mypy across 103 source files — passed.
- `scripts/check_conformance.py` — passed traceability checks.
- `git diff --check` — passed.

Hosted Quality at `a75e47a` passed 1,809 tests with 28 skips. Both canonical
fixture variants completed a real `pg_dump`/`pg_restore` round trip and passed
all deterministic projection, snapshot and report comparisons. Credential
sentinel exclusion, recovery bootstrap and fresh authority epoch rotation remain
open in later M2 slices.
