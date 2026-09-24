# Authority Epoch Replacement — M1.6

Date: 24 September 2026.
Status: passes 1-2 implemented locally. M1 exit-gate evidence remains open.

## Scope

M1.6 pass 1 adds `ReplaceAuthorityEpoch`, `AuthorityEpochReplacementResult` and
`AuthorityEpochReplacementService.replace`. The service creates a new authority
epoch only after protected restoration has completed. It does not rewrite old
audit attribution and does not delete historical authorization, recovery or
transition records.

The replacement transaction requires:

- current security state is NORMAL;
- recovery bootstrap is not pending;
- current epoch matches the command;
- current security-state version matches the command;
- requested replacement epoch is non-nil and different from the current epoch;
- a valid restoration transition audit exists for the supplied restoration ID;
- reason code is `RECOVERY_VERIFIED`.

On success, the service updates `security_state.authority_epoch_id`, increments the
security-state version and appends a same-state `NORMAL -> NORMAL`
`security_state_transitions` audit row attributed to `security_recovery_service`.
The old epoch remains present on all earlier audit and authorization records.

## Semantics

Epoch replacement means new authority-bearing effects must use the new epoch.
Existing operator and execution authorization records remain historical evidence,
but fresh validation against current authority fails because their epoch no longer
matches. Exact historical replay remains allowed only as history, not as permission
for new effects.

Pass 1 proves this for the local authorization validation boundary. Pass 2 adds
`AuthorizationService.require_current_execution`, a consumer boundary for protected
effects that loads the current authority epoch, decodes operator and execution
authorization history, re-runs freshness validation, and optionally checks the
required RecoveryContext and capability.

`issue_execution` remains an exact-replay and historical issuance API. Callers that
intend to perform an authority-bearing effect must use
`require_current_execution` so stale, expired, wrong-context or wrong-capability
authorization records fail before the effect.

## Limits

This pass does not add a dedicated epoch-replacement table, does not cryptographically
link old and new epochs, does not perform backup reconstruction and does not inspect
every downstream consumer beyond the trusted authorization-service boundary. Those
are reserved for the remaining M1.6 pass and the exit gate.

## Verification

Focused PostgreSQL tests in
`tests/integration/test_authority_epoch_replacement_service.py` cover:

- successful replacement after protected restoration;
- authoritative audit row and security-state epoch/version update;
- old execution authorization failing fresh validation against the new epoch;
- exact historical replay of an old execution authorization after epoch
  replacement;
- `require_current_execution` rejection for old-epoch execution authorization;
- `require_current_execution` acceptance for newly issued execution authorization
  in the replacement epoch;
- invalid restoration audit denial;
- repeated stale replacement denial;
- audit failure rollback preserving old epoch/version.

Local evidence for pass 2: authorization contract/service and epoch replacement
focused tests passed 39 tests. Broader M1 stack, lint, type and migration evidence
remain to be refreshed for the exit-gate pass.
