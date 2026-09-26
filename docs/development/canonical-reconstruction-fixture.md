# Canonical Reconstruction Fixture — M2.6

> Dated execution and verification record. Status and remaining-work statements below describe this checkpoint; use the maintained [current source of truth](source-of-truth.md) and [roadmap](roadmap.md) for present claims.

Date: 25 September 2026.
Status: canonical reconstruction fixture implemented locally.

## Scope

M2.6 adds a compact integration fixture in
`tests/integration/m2_reconstruction_fixture.py`.

The fixture seeds one source database with representative records for:

- investigation, cycles and cycle attempts;
- source evidence, claims, provenance and assessments;
- source-dependence projection and immutable change history;
- governed memory change history;
- stopping decision projection and immutable history;
- provider/report-generation attempt state;
- security transition history and current Authority Epoch metadata;
- RecoveryContext and recovery-context audit history;
- OperatorAuthorization and ExecutionAuthorization history plus audit rows;
- task-scoped research audit, trusted-source policy audit and provider-session
  audit rows.

It also provides a `restrictive_unresolved` variant that leaves the database in
`LOCKDOWN` with an interrupted cycle attempt, an `UNKNOWN` provider attempt and
a RecoveryContext payload that records the unresolved operation.

## Boundary

The fixture is test support only. It does not perform backup, restore,
equivalence comparison, recovery bootstrap, restoration or epoch replacement.
Its purpose is to give later M2 slices one stable, intentionally rich source
state for reconstruction and comparison coverage.

## Verification

Local M2.6 verification:

- `python -m pytest tests/integration/test_m2_reconstruction_fixture.py` — 2 passed.
- `python -m ruff check tests/integration/m2_reconstruction_fixture.py tests/integration/test_m2_reconstruction_fixture.py` — passed.
