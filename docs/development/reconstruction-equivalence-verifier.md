# Reconstruction Equivalence Verifier — M2.7

Date: 25 September 2026.
Status: deterministic reconstruction equivalence helpers implemented locally.

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

This slice does not yet perform the full `pg_dump`/`pg_restore` round trip,
credential sentinel scan, recovery bootstrap or epoch rotation.

## Verification

Local M2.7 verification:

- `python -m pytest tests/integration/test_m2_reconstruction_fixture.py tests/integration/test_m2_reconstruction_equivalence.py` — 4 passed.
- Combined M2.1-M2.7 suite — 59 passed, 2 skipped because `pg_dump` and `pg_restore` are unavailable in the local environment.
- Ruff — passed.
- Mypy across 103 source files — passed.
- `scripts/check_conformance.py` — passed traceability checks.
- `git diff --check` — passed.

Closeout boundary: this is local implementation evidence for deterministic projections and the canonical fixture. Hosted CI verification, a full `pg_dump`/`pg_restore` round trip, credential sentinel exclusion, recovery bootstrap, and fresh authority epoch rotation remain open in later M2 slices.
