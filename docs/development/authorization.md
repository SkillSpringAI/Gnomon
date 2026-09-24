# OperatorAuthorization And ExecutionAuthorization — M1.2/M1.3

Date: 24 September 2026.
Status: domain contract and trusted local issuance/persistence implemented
locally. Restoration consumption and hosted verification remain open.

## Scope

This pass defines frozen, bounded authorization artifacts in
`src/research_agent/domain/authorization.py`.

`OperatorAuthorization` separates operator identity from authority. It records:

- authorization ID;
- local or authenticated principal identity;
- explicitly granted authority-bearing capability;
- bounded scope;
- authority epoch;
- issuance basis;
- issuance and expiry times;
- replay identity;
- optional RecoveryContext binding.

`ExecutionAuthorization` binds one bounded execution attempt to an existing
operator authorization and the authority epoch under which it was issued.

These artifacts are evidence. They do not authenticate a principal, issue a grant,
perform capability checks, clear the recovery fence or authorize restoration by
themselves.

## Boundaries

Only `recovery_action` and `authority_administration` are modeled as explicit
authority-bearing grants in this first pass. Ordinary mutation, provider dispatch
and broad runtime execution are intentionally outside this contract.

RecoveryContext binding is optional but, when present, it must appear both in the
authorization scope and in the issuance basis. This prevents possession of a
RecoveryContext from silently becoming permission.

Execution authorization cannot:

- change the granted capability;
- expand the operator scope;
- outlive the operator authorization;
- bind to a different operator authorization;
- survive an authority epoch change.

## Validation

`validate_operator_authorization` checks:

- non-stale authority epoch;
- timezone-aware clock;
- current validity window;
- optional RecoveryContext binding.

`validate_execution_authorization` revalidates the operator authorization, then
checks execution epoch, parent binding, capability equality, scope narrowing and
validity bounds.

Both functions are pure validation helpers. A future service must still load the
current authority basis from trusted state and perform point-of-effect capability
checks under its own transaction.

## Verification

Focused local tests in `tests/unit/test_authorization_contract.py` cover immutable
round trips, invalid principals, invalid/nil identifiers, invalid capabilities,
scope bounds, duplicate basis/scope rejection, stale epoch, expiry, RecoveryContext
binding, execution scope escalation, parent mismatch, capability change and copied
model revalidation.

Local evidence for pass 1: 25 focused tests passed. Ruff passed for the new domain
and test files. Strict mypy passed across 91 source files.

## Trusted issuance and persistence pass

`AuthorizationService` is an internal local issuance boundary. It accepts a
database engine, owns each transaction, reads the current authority epoch from the
trusted security-state singleton, and records local authorization artifacts without
consuming them for recovery restoration.

Issuance commands contain caller-retained artifact IDs, expected authority epoch,
scope, expiry and replay IDs. The service supplies issuance time and current
security-state version. New issuance fails closed when the expected epoch is stale,
the request is expired or malformed, or execution scope attempts to exceed the
operator authorization. Exact replay with the same command returns historical
records; reusing an authorization identity for a different command is rejected.

Each transaction uses PostgreSQL REPEATABLE READ and a security-row SHARE lock.
`operator_authorizations`, `execution_authorizations` and `authorization_audit`
are append-only application records introduced by migration 034. Audit failure
rolls back the authorization insert, and a denied or rolled-back command does not
create replayable history.

Reads and replay validate the stored authorization payload against the row columns,
the retained command and the audit record. Malformed history fails without repair.
Historical replay can return an otherwise stale authorization only when the
original command exactly matches. `require_current_execution` is the current-use
boundary for protected effects: it loads the trusted current authority epoch,
decodes the stored execution and parent operator authorization, re-runs freshness
validation, and can require a specific RecoveryContext and capability before
returning the execution authorization.

Local evidence for pass 2 plus closeout hardening: the combined authorization
unit/integration suite passed 33 tests. Ruff passed for the touched authorization
files. Strict mypy passed across 93 source files.

## Remaining Work

M1.4-M1.6 now consume authorization artifacts for reconciliation/restoration and
post-restoration epoch replacement. This contract still does not add authenticated
multi-operator identity, cryptographic tamper resistance or backup reconstruction.
Milestone 1 remains open.

Known issues that must be reviewed before the M1.6 exit gate are tracked in the
[M1 authorization gap register](m1-authorization-pre-m1.6-gap-register.md).
