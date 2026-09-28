# C3a Pass 3A — Reconstruction validation-pending foundation

Date: 28 September 2026. Pass 3A only; reconstruction ordering and authority application remain unchanged.

## Implemented contract

Migration `035_reconstruction_validation_pending.sql` adds `security_state.reconstruction_validation_pending BOOLEAN NOT NULL DEFAULT FALSE`. Existing valid ordinary and recovery databases therefore retain their previous behavior. A database check permits `TRUE` only with a pending recovery bootstrap, present origin metadata and a current version greater than the origin version. The persisted security-state loader validates the same relationship and exposes the boolean without changing effective-state calculation. It does not infer validation from this field: `TRUE` means validation is outstanding; `FALSE` is not proof of M2 source/restored equivalence.

`AuthorityBootstrapService` validates the field before startup changes and preserves it on recovery or continuing startup. The existing transition service cannot transition a pending-bootstrap row, and the new database constraint prevents protected restoration from clearing the bootstrap while validation remains pending. `RecoveryRestorationService` also rejects that case explicitly. Reconstruction-specific code is the intended future owner of setting and clearing the field. The current reconstruction implementation neither sets it nor changes phase order; its existing unfenced interval remains until Pass 3B.

RecoveryContext capture checks the singleton field under its existing SHARE lock before the idempotent replay branch. Current-context reads reject while pending, while historical reads remain available. New recovery-bound operator/execution issuance rejects while pending under its existing authority lock; exact historical replay remains historical-only. `require_current_execution()` retains its bounded helper contract. Backup inspection rejects a pending source. The default backup creation path rechecks under a singleton SHARE lock after `pg_dump` and holds it through publication, rejecting a target that became pending during the dump. Injected test inspectors remain trusted test dependencies.

## Verification and limits

The new integration module covers migration from pre-035 ordinary and pending-bootstrap databases, the false default, valid persistence and rerun, invalid combinations at SQL and loader boundaries, continuation/startup preservation, denied context capture and replay, denied new authorization issuance, backup rejection including a mid-dump state change, and inability to clear the gate through security transition or protected restoration. Legacy pre-033/pre-034/epoch fixture tests now install 035 before using the current mapped singleton; their original upgrade assertions remain.

Focused selections: 447 passed, 4 environment-dependent skips across reconstruction, security, recovery, authorization, backup and migration tests. `python -m ruff check .`, `python -m mypy src`, formatter checks for changed files, `python scripts/check_conformance.py`, and `git diff --check` passed. This is local verification, not hosted Quality.

Pass 3B still must atomically install manifest S/V/E with the recovery fence and `reconstruction_validation_pending=true` before the data-producing `pg_restore`, preserve that state across import/migration failures, perform the bounded production checks, and publish `false` in a validated transaction before fresh context capture. It must adapt the M2 equivalence drill's raw authority assertion without weakening its other projections. No C3b extraction or public restore-only path is part of this pass.
