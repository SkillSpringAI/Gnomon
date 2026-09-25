# Backup State Inspection — M2.2

Date: 25 September 2026.
Status: read-only inspection service implemented locally.

## Scope

M2.2 adds `BackupStateInspectionService`, a read-only service that gathers the
database, application, migration and authority metadata required before a backup
manifest can be created.

This slice does not invoke `pg_dump`, write backup files, publish manifests,
perform restore preflight or mutate application state.

## Semantics

The service opens a repeatable-read, read-only transaction and returns:

- PostgreSQL database metadata;
- explicitly supplied application version and source revision;
- ordered migration entries from `research_agent_schema_migrations`;
- current security state, security-state version and Authority Epoch.

The service reuses M2.1 manifest metadata value objects. Malformed migration
history, unsupported PostgreSQL major versions, missing security state and invalid
authority lineage fail closed through `BackupStateInspectionUnavailable`.

## Limits

The service accepts the build/source revision as trusted caller input. Binding that
value to packaging or release metadata remains later M2 work. Dump hashing,
credential exclusion, restore compatibility and reconstruction equivalence remain
future slices.

## Verification

Local M2.2 verification:

- `python -m pytest tests/integration/test_backup_state_inspection_service.py` — 8 passed.
- `python -m ruff check src/research_agent/application/backup_state_inspection_service.py tests/integration/test_backup_state_inspection_service.py` — passed.
- `python -m mypy src` — passed across 98 source files.
