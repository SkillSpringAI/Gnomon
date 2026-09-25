# Backup Creation Boundary — M2.3

Date: 25 September 2026.
Status: trusted backup creation boundary implemented locally.

## Scope

M2.3 adds `BackupCreationService` and `scripts/backup_postgres.py`.

The service:

- reuses M2.2 read-only state inspection;
- generates a backup ID when one is not supplied;
- invokes `pg_dump` with an argument list, not shell interpolation;
- writes `database.dump`;
- computes the dump SHA-256;
- writes `manifest.json` using the M2.1 manifest contract;
- publishes the backup directory only after both dump and manifest are complete.

If any stage fails, the temporary working directory is removed and the requested
backup directory is not published.

## Credential Boundary

The service does not put database passwords in subprocess arguments or manifest
content. It removes `DATABASE_URL` from the child process environment and, when a
password is present in the SQLAlchemy URL, supplies only `PGPASSWORD` to `pg_dump`.

## Limits

This slice does not implement restore preflight, `pg_restore`, reconstruction
equivalence, credential sentinel database scans, or post-reconstruction epoch
rotation. The real `pg_dump` integration test is present but skips on systems
where the `pg_dump` binary is unavailable.

## Verification

Local M2.3 verification:

- `python -m pytest tests/unit/test_backup_creation_service.py tests/integration/test_backup_creation_pg_dump.py` — 6 passed, 1 skipped (`pg_dump` unavailable).
- `python -m ruff check src/research_agent/application/backup_creation_service.py scripts/backup_postgres.py tests/unit/test_backup_creation_service.py tests/integration/test_backup_creation_pg_dump.py` — passed.
- `python -m mypy src` — passed across 99 source files.
