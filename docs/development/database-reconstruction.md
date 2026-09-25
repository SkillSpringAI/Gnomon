# Database Reconstruction — M2.5

Date: 25 September 2026.
Status: guarded database reconstruction implemented locally.

## Scope

M2.5 adds `DatabaseReconstructionService` and `scripts/restore_postgres.py`.

The service:

- reuses M2.4 restore preflight before any import;
- invokes `pg_restore` with an argument list, not shell interpolation;
- restores data only into a pristine, already migrated PostgreSQL target;
- disables owner and privilege restoration;
- runs the restore in one `pg_restore` transaction with exit-on-error enabled;
- filters the archive table of contents with `pg_restore --list`/`--use-list`
  to exclude migration-table and `security_state` data;
- orders table-data entries by the migrated target's foreign-key dependencies
  so parent rows exist before dependent rows are copied;
- writes the manifest authority metadata into the canonical `security_state`
  row only after `pg_restore` succeeds;
- reruns local migrations after import;
- verifies migration, security-state and task-table accessibility;
- verifies restored authority metadata through M2.2 state inspection.
- enters the existing M1 recovery bootstrap and captures a new RecoveryContext
  before the operator entry point reports success.

The migration ledger is retained from the preflighted target. This keeps the
target schema under the locally reviewed migration set and avoids importing old
or duplicate migration rows. Newer empty schema objects remain a compatibility
policy detail for later equivalence work.

The 25 September hosted quality failure exposed an unsupported
`--exclude-table-data` flag on `pg_restore` 16. That flag belongs to `pg_dump`.
The restore now filters the archive's table of contents before import and keeps
the pristine-target preflight; it does not clear target tables. Hosted
Quality confirmed the archive filtering correction at `ced74f7`. The expanded
M2.7 fixture then exposed foreign-key ordering across table-data entries. The
dependency ordering change and both canonical restore variants passed hosted
Quality at `a75e47a`.

## Authority Boundary

The operator path enters governed recovery after verified import. It does not
start ordinary application authority, issue operator or execution authorization,
clear recovery fences or rotate the Authority Epoch. Those remain later M2 slices.

## Credential Boundary

The service removes `DATABASE_URL` from the child process environment and, when
the SQLAlchemy URL contains a password, supplies it only through `PGPASSWORD`.
The password is not included in process arguments.

## Limits

The real `pg_restore` integration drill is present but skips when either
`pg_dump` or `pg_restore` is unavailable. Full reconstruction equivalence,
credential sentinel scans, recovery bootstrap integration and post-restoration
epoch replacement remain deferred.

## Verification

Local M2.5 verification:

- `python -m pytest tests/unit/test_database_reconstruction_service.py tests/integration/test_database_reconstruction_integration.py` — 5 passed, 1 skipped (`pg_dump`/`pg_restore` unavailable).
- `python -m ruff check src/research_agent/application/database_reconstruction_service.py scripts/restore_postgres.py tests/unit/test_database_reconstruction_service.py tests/integration/test_database_reconstruction_integration.py` — passed.
