# Recovery Reconciliation — M1.4

> Dated execution and verification record. Status and remaining-work statements below describe this checkpoint; use the maintained [current source of truth](source-of-truth.md) and [roadmap](roadmap.md) for present claims.

Date: 24 September 2026.
Status: read-only local reconciliation verdict implemented. Protected restoration,
fence clearing and authority epoch replacement remain open.

## Scope

M1.4 adds `RecoveryReconciliation` verdicts and `RecoveryReconciliationService`.
The service consumes a stored RecoveryContext, re-reads current authority under the
security-state SHARE lock, re-enumerates the supported evidence and operation
streams, and returns a deterministic verdict. It does not write recovery records,
repair history, clear RECOVERY_REQUIRED, create a new authority epoch or authorize
restoration by itself.

The verdict covers the five checks already required by RecoveryContext:

- authority lineage;
- history integrity;
- evidence integrity;
- operation outcomes;
- configuration integrity.

`restoration_allowed` can be true only when every check is `passed`. A `failed` or
`unknown` check blocks restoration consumers.

## Deterministic Outcomes

Authority lineage passes only while the context is current and unexpired against
trusted runtime state. Stale authority version, changed epoch, cleared bootstrap
metadata or expiry produce a failed authority-lineage check.

History integrity confirms that captured evidence references still resolve in the
supported history streams. Evidence integrity separately requires the current
supported evidence inventory to match the captured complete inventory. Added or
removed supported evidence fails the check; partial inventory remains unknown.

Operation outcomes revisit captured unresolved operations and any currently
unresolved supported operations. Provider attempts are classified as:

- `SUCCEEDED` -> committed;
- `FAILED` -> did_not_commit;
- any other status -> unknown.

Cycle attempts are classified as:

- `COMPLETED`, `FAILED`, `BLOCKED` or `INTERRUPTED` -> committed terminal outcome;
- any other status -> unknown.

New unresolved operations after context capture fail reconciliation because the
context no longer describes all supported unresolved work. Missing captured
operation rows are treated as did_not_commit evidence for this local verdict, but
database-owner tampering remains outside the guarantee.

## Limits

This pass is intentionally bounded to the streams already captured by
RecoveryContext: security transitions, research events, memory changes, source
relationship changes, stopping decision changes, provider attempts and cycle
attempts. It does not prove semantic evidence correctness, task ownership for every
referenced record, live network outcomes, external provider truth, credential
state, backup reconstruction, authenticated operator identity or cryptographic
tamper resistance.

Configuration integrity is limited to the supported local configuration boundary:
the context must remain bound to singleton security state 1 and complete supported
inventory. Broader configuration drift remains a later operational/release concern.

## Verification

Focused PostgreSQL tests in `tests/integration/test_recovery_reconciliation_service.py`
cover:

- successful reconciliation after unknown provider and cycle attempts become
  terminal;
- unresolved operations remaining unknown and blocking restoration;
- evidence added after capture failing reconciliation;
- captured history deleted after capture failing without repair;
- stale authority basis failing reconciliation.

Local evidence for this pass: the recovery reconciliation, recovery context and
RecoveryContext unit suites passed 51 focused tests. Ruff passed for the touched
recovery files. Strict mypy passed across 94 source files.
