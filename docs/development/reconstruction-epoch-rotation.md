# Reconstruction Epoch Rotation — M2.10

Date: 25 September 2026.
Status: local verification complete; hosted Quality pending.

The supported reconstruction completion path is
`RecoveryRestorationService.complete_reconstruction`. It runs M1.5 protected
restoration and M1.6 Authority Epoch replacement in one database transaction.
Both transition audits must persist before the recovery fence clears and the
new `NORMAL` authority becomes visible. An epoch audit failure rolls back the
restoration, leaving `RECOVERY_REQUIRED` and its bootstrap fence in place.

The real PostgreSQL reconstruction drill now completes the baseline fixture
through this path. It verifies that the restored epoch remains on historical
authorization records, an exact replay of a pre-rotation authorization returns
history only, and `require_current_execution` rejects that authorization.
A new operator and execution authorization issued under the replacement epoch
can be used for current effects. The restrictive unresolved fixture still
cannot complete restoration or rotate its epoch.

The separate M1.5 `complete` and M1.6 `replace` methods remain available for
ordinary recovery. Reconstruction callers must use `complete_reconstruction`
so there is no committed interval of `NORMAL` authority under the restored
epoch. This boundary does not protect against direct database writes or a caller
deliberately choosing the ordinary recovery API for a reconstructed database.
