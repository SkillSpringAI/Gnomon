# C2 Recovery Shared-Read Boundary — Local Verification Assessment

Date: 27 September 2026.
Baseline: clean `main` at `e84ff8e`.
Scope: Pass 1 characterization, Pass 2 authority-basis extraction, Pass 3 inventory
extraction, and Pass 4 integration verification. No C3 work is included.

## Verification state

Assessment: **COMMIT READY**, with the local host limitations below. This is not
hosted verification or formal closure.

- Implementation exists locally in the working tree.
- C2 has not been committed; there is no implementation SHA to cite yet.
- Hosted Quality and browser verification at a C2 SHA remain pending.
- C2 is not formally closed. Historical C1/M1/M2 hosted results do not verify C2.

## Production review

`recovery_authority_basis.py` provides
`read_recovery_authority_basis(session, record, *, unavailable,
missing_record_message=None)`. It owns the second effective-state load, origin
construction and current `RecoveryAuthorityBasis` construction. Context and
restoration retain their lock acquisition and READ_AUDIT prerequisite.

`recovery_inventory.py` provides `read_supported_recovery_inventory(session)`.
Context capture uses its retained `_inventory` forwarding wrapper; reconciliation
and restoration's existing private `_reconcile` call the shared primitive directly.
Historical context reads continue validating their persisted inventory payload.

The full diff against `e84ff8e`, including new files, shows no recovery policy or
externally visible semantic change. An AST comparison confirms the inventory body
is identical to baseline and 21 surrounding transaction, freshness, reconciliation,
disposition and mutation methods remain identical. Basis-reader lock queries are
AST-identical, including capability prerequisites; the context state/origin/basis
sequence is also AST-identical after substituting the caller exception name.
Context/reconciliation use SHARE; restoration uses FOR UPDATE with
populate_existing and retains the same mutable row through mutation. Transaction
ownership, REPEATABLE READ, lock lifetime and exception translation remain local to
the services.

Validation order remains lock, READ_AUDIT (including its state load), second
refreshed state load, locked-row check, origin construction and basis validation.
Capability denial still precedes reader-specific missing-origin checks for malformed
persisted metadata. Domain validation exceptions still propagate. Effective
RECOVERY_REQUIRED, authority epoch and version identity, freshness and separate
recovery authorization are unchanged. Diagnostic reads grant no authority.

Inventory still reads five global evidence streams and two operation streams without
task/epoch filters. Kind precedence, UUID ordering, LIMIT 101 per query, separate
aggregate 100-item limits, truncation and whole-inventory PARTIAL behavior are
unchanged. Only explicit terminal statuses are excluded; unfamiliar statuses and
provider EXPIRED remain unknown. Provider FAILED means did_not_commit; terminal
cycle FAILED/BLOCKED/INTERRUPTED mean committed. Reconciliation/restoration assembly
is unchanged apart from the inventory call. One expression was reformatted by Ruff.
There are no schema, migration, API, domain or other production changes.

## Characterization assessment

Pass 1 added 29 parametrized cases across three files without replacing existing
tests:

- `tests/unit/test_recovery_basis_reads.py`: 18 exception-boundary cases for both
  current-basis readers, including absent authority, missing/malformed origin,
  retained metadata, equal origin/current version and naive timestamps.
- `tests/integration/test_recovery_context_service.py`: three consumer lock/isolation
  cases and one aggregate-bound, mixed-evidence-order, PARTIAL and restoration-parity
  case, including a historical partial capture against later complete inventory.
- `tests/integration/test_recovery_reconciliation_service.py`: seven status cases
  covering PENDING, DISPATCHED, EXPIRED, unfamiliar values, provider FAILED and
  terminal cycle FAILED/BLOCKED/INTERRUPTED.

These assert pre-extraction contracts, not new helper names or internal call counts.
Existing tests retain evidence overflow, snapshot isolation, capture lock lifetime,
rollback, freshness, authorization and terminal completion coverage. No useful
characterization was removed or weakened in Passes 2–4.

The mock basis tests and lock/parity tests use existing private caller methods.
Future legitimate changes to those methods or Session access may require adapting
the harness while retaining the behavioral assertions. The reconciliation lock case
tests its transaction with the shared basis reader directly; public reconcile tests
and diff review separately confirm consumer wiring. The inventory wrapper remains
an intentional test interception point, not a second inventory implementation.

## Local verification

Commands and results are recorded against the uncommitted C2 working tree:

| Check | Result |
|---|---|
| Focused recovery/security/reconstruction tests, `python -m pytest -ra` with the files listed below | 1,349 passed, 3 skipped, 42 deprecation warnings |
| Normal full suite, `python -m pytest -ra` | 1,844 passed, 32 skipped, 633 warnings in 419.41 seconds |
| `python -m ruff check .` | Passed |
| `python -m ruff format --check` on all eight changed Python files | Passed |
| `python -m mypy src` | Passed, 103 source files |
| `git diff --check` | Passed |
| `python -m research_agent.cli migrate` | Passed, zero pending migrations |
| `python scripts/smoke_test.py` | Passed |
| `python scripts/verify_prototype.py` | Passed: 34 fresh migrations, no-op rerun, real HTTP lifecycle/cycles/blocked outcome and restart persistence including authority epoch |
| `python scripts/check_conformance.py` | Passed authority hashes, section coverage and evidence references; traceability only |
| `python scripts/verify_wheel.py --database` | Passed clean base install/dependencies, all 34 resource checksums, concurrent fresh migration, populated upgrade, rerun, drift rejection and database draft |
| `python scripts/verify_wheel.py` | Passed clean base wheel installation, dependency check, all 34 migration checksums and memory API/provider behavior without AWS |

Focused unit files: `test_recovery_basis_reads.py`, `test_recovery_context.py`,
`test_security_state_store.py`, `test_security_state.py`, `test_security_capability.py`,
`test_security_transition_policy.py`, `test_authorization_contract.py`,
`test_database_reconstruction_service.py`.

Focused integration files: `test_recovery_context_service.py`,
`test_recovery_reconciliation_service.py`, `test_recovery_restoration_service.py`,
`test_authority_bootstrap.py`, `test_authority_epoch.py`,
`test_authority_epoch_replacement_service.py`, `test_authorization_service.py`,
`test_security_state_transitions.py`, `test_security_api.py`, `test_cycle_recovery.py`,
`test_persistence_invariants.py`, `test_database_reconstruction_integration.py`,
`test_m2_reconstruction_fixture.py`, `test_m2_reconstruction_equivalence.py`,
`test_backup_credential_sentinels.py`.

The focused skips are two real reconstruction variants and one credential-sentinel
drill requiring unavailable pg_dump/pg_restore. Mocked mechanics/equivalence tests
are not substitutes for those real client-tool cases. RUN_BROWSER_TESTS is unset;
the normal suite intentionally skips opt-in browser cases. No C2 browser or hosted
verification is claimed. Quality must run its checks, minimal-install and browser
jobs against the eventual exact C2 commit, including zero skips in all 28 browser
cases and the real PostgreSQL-client cases absent locally.

The full suite's 32 skips comprise 28 browser cases plus four real client-tool
cases: backup creation, two reconstruction variants, and the credential-sentinel
drill. Focused verification took 197.51 seconds. Full-suite warnings include
FastAPI startup deprecations and a Pydantic field-alias warning; no warning cleanup
was attempted within C2. No verification defect required further production or
test changes in Pass 4.

## Closure hygiene and excluded debt

The maintained source-of-truth, implementation-status and roadmap now distinguish
local C2 implementation from pending commit/hosted verification. Dated M1/M2/C1
records remain historical and unchanged. Before formal closure, record the exact
implementation SHA and hosted Quality/browser results here, update the maintained
status/roadmap accordingly, and add the completed checkpoint to development history.
Do not advance to C3 as part of this assessment.

Excluded debt remains: restoration's private cross-service reconciliation and
`__new__` construction, duplicated reconciliation assembly, the context inventory
compatibility/test wrapper, separate caller READ_AUDIT prerequisites, reconstruction
mechanics consolidation, wider deployment recovery, database-role separation,
ambiguous commits and privileged-tamper evidence. Inventory scope and bounds remain
intentional limitations, not omissions to repair within C2.
