# Protected Recovery Restoration — M1.5

Date: 24 September 2026.
Status: protected restoration preflight and fence-clearing transition implemented
locally. Authority epoch replacement remains M1.6 work.

## Scope

M1.5 adds `PrepareProtectedRestoration`, `PreparedProtectedRestoration`,
`ProtectedRestorationResult`, `RecoveryRestorationService.prepare` and
`RecoveryRestorationService.complete`. The service validates all restoration
preconditions together in one transaction and can then clear the recovery-bootstrap
fence with an authoritative security-transition audit.

This pass intentionally supports only `RECOVERY_REQUIRED -> NORMAL` restoration
with `RECOVERY_VERIFIED`. Partial restoration to DEGRADED remains later work unless
explicitly designed and tested.

## Preconditions

The preflight owns a REPEATABLE READ transaction and locks the singleton
`security_state` row FOR UPDATE. It then requires:

- current authority epoch matches the command;
- current security-state version matches the command;
- recovery bootstrap is still pending;
- RecoveryContext exists, decodes and remains bound to the current basis;
- M1.4 read-only reconciliation passes in the same transaction;
- OperatorAuthorization and ExecutionAuthorization exist and decode;
- execution authorization is current, epoch-bound and scoped under the operator
  authorization;
- both authorizations are bound to the same RecoveryContext;
- execution authorization grants `recovery_action`.

Any stale version, stale epoch, failed/unknown reconciliation, malformed context,
missing authorization or mismatched RecoveryContext binding fails closed and leaves
the recovery fence unchanged.

## Completion

`complete` re-runs the preflight inside its own locked transaction before changing
state. On success it:

- sets the canonical security state to raw NORMAL;
- clears `recovery_bootstrap_pending` and bootstrap-origin metadata;
- increments the security-state version;
- appends a `security_state_transitions` audit row from effective
  RECOVERY_REQUIRED to NORMAL with `security_recovery_service` attribution;
- records restoration, context and authorization IDs in `related_event_ids`.

Audit failure rolls back the state update. A repeated command after success fails
closed because recovery bootstrap is no longer pending.

## Limits

The prepared artifact is evidence that preconditions held at `checked_at`; it is
not persisted and is not a replay token. `complete` therefore re-reads and
revalidates everything.

This pass does not create a new authority epoch, invalidate old execution
authorizations, alter provider/cycle attempts, reconstruct backup state or add
authenticated multi-operator identity. Those questions remain M1.6 or later work.

## Verification

Focused PostgreSQL tests in `tests/integration/test_recovery_restoration_service.py`
cover:

- successful preflight after reconciliation passes and authorizations bind to the
  RecoveryContext;
- no RECOVERY_REQUIRED fence clearing during pass 1;
- successful protected completion that clears the fence and appends audit;
- audit failure rolling back fence clearing;
- repeated completion failing closed after success;
- unresolved operations blocking preflight;
- stale expected security-state version blocking preflight;
- authorizations bound to a different RecoveryContext blocking preflight.

Local evidence: the focused restoration suite passed 7 tests. The combined
M1.1-M1.5/authorization stack passed 88 tests before completion and will be rerun
after this documentation update. Ruff passed for the touched restoration files.
Strict mypy passed across 95 source files.
