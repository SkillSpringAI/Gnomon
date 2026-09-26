# Authority Epoch Replacement — M1.6

> Dated execution and verification record. Status and remaining-work statements below describe this checkpoint; use the maintained [current source of truth](source-of-truth.md) and [roadmap](roadmap.md) for present claims.

Date: 24 September 2026.
Status: passes 1-3 implemented and hosted-verified for the bounded local M1 scope.

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
link old and new epochs and does not perform backup reconstruction. Those are
reserved for M2. Pass 3 audited the local M1 recovery/authorization consumers:
restoration revalidates authorization evidence under the locked current authority
epoch before clearing the fence, epoch replacement requires restored audit evidence,
and new protected effects should use `require_current_execution` rather than
historical issuance replay.

## Exit-Gate Evidence Map

The M1.6 exit gate requires restrictive recovery entry, deterministic
reconciliation, separately authorized restoration, correct authority epoch
replacement and audit preservation without making recovery a superuser mode. Local
coverage is:

| Exit-gate/adversarial item | Evidence |
| --- | --- |
| Restrictive recovery bootstrap entry | `tests/integration/test_authority_bootstrap.py::test_recovery_bootstrap_fences_restored_authority_before_reconciliation` |
| Stale RecoveryContext and stale authority basis | `tests/unit/test_recovery_context.py::test_stale_context_rejected_against_independent_current_basis`; `tests/integration/test_recovery_context_service.py::test_no_capture_outside_bootstrap_and_epoch_change_rejects_old_basis` |
| Unknown provider/cycle outcome blocks restoration | `tests/integration/test_recovery_reconciliation_service.py::test_reconciliation_blocks_while_operations_remain_unknown`; `tests/integration/test_recovery_restoration_service.py::test_prepare_rejects_until_reconciliation_passes` |
| Missing/new evidence fails read-only reconciliation | `tests/integration/test_recovery_reconciliation_service.py::test_reconciliation_detects_evidence_added_after_context_capture`; `test_reconciliation_detects_missing_captured_history_without_repair` |
| Protected restoration consumes current context, reconciliation and authorization | `tests/integration/test_recovery_restoration_service.py::test_complete_protected_restoration_clears_fence_and_writes_audit` |
| Stale version, repeated command and audit failure do not clear the fence | `test_prepare_rejects_stale_expected_version`; `test_complete_protected_restoration_rejects_repeated_command_after_success`; `test_complete_protected_restoration_rolls_back_when_audit_fails` |
| Stale operator/execution artifacts and old-epoch replay cannot authorize current effects | `tests/unit/test_authorization_contract.py::test_operator_authorization_rejects_stale_epoch_time_and_context`; `test_execution_authorization_rejects_stale_or_escalating_artifacts`; `tests/integration/test_authorization_service.py::test_old_epoch_operator_cannot_issue_new_execution_authorization`; `tests/integration/test_authority_epoch_replacement_service.py::test_epoch_replacement_splits_historical_replay_from_current_execution` |
| Epoch replacement requires restored audit evidence and preserves rollback on audit failure | `tests/integration/test_authority_epoch_replacement_service.py::test_replace_authority_epoch_requires_restoration_audit`; `test_replace_authority_epoch_rolls_back_when_audit_fails` |
| Restrictive transition races and point-of-effect authority checks fail closed | `tests/integration/test_security_state_transitions.py::test_concurrent_transitions_cannot_consume_one_version_twice`; `test_restrictive_transition_blocks_in_flight_result_persistence` |
| Model/external-agent attempts cannot manufacture recovery authority | `tests/unit/test_recovery_context.py::test_invalid_or_authority_bearing_context_is_rejected`; `tests/unit/test_authorization_contract.py::test_invalid_operator_authorization_is_rejected` |

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

Pass-3 local verification completed with 122 focused M1 authority tests passing,
conformance checks passing, Ruff passing, mypy passing for 96 source files,
zero pending migrations, and a clean `git diff --check`. Hosted Quality run
`35981852013` verified closeout SHA `316c90bf1816743ce73571e907b5c24e4da6cdec`
with `checks`, `minimal-install`, and `browser` all passing.
