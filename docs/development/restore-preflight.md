# Restore Preflight — M2.4

Date: 25 September 2026.
Status: restore preflight validation implemented locally.

## Scope

M2.4 adds `RestorePreflightService`.

The service validates backup material before any `pg_restore` execution:

- loads and validates `manifest.json` through the M2.1 manifest contract;
- requires `database.dump` to exist;
- recomputes the dump SHA-256 and compares it with the manifest;
- inspects the target database through M2.2 state inspection;
- rejects incompatible PostgreSQL major versions;
- rejects backup schemas newer than the target;
- rejects migration checksum drift;
- rejects populated restore targets.

The pristine-target check allows only canonical bootstrap metadata required by a
migrated target database: `research_agent_schema_migrations` and the singleton
`security_state` row. Application data, history, audit, authorization,
provider, source, claim, memory, task and recovery rows must be absent.

## Authority Boundary

This slice does not import data, run `pg_restore`, enter recovery mode, issue
authority, replace the Authority Epoch or clear any recovery fence. It only
fails closed before reconstruction if the backup material or target database is
not acceptable for the supported restore path.

## Limits

Source revision metadata and Authority Epoch metadata are validated structurally
by the manifest contract and target inspection. Semantic source-revision policy,
database reconstruction, equivalence comparison, credential sentinel scans and
post-reconstruction recovery authority remain deferred to later M2 slices.

## Verification

Local M2.4 verification:

- `python -m pytest tests/integration/test_restore_preflight_service.py` — 8 passed.
- `python -m ruff check src/research_agent/application/restore_preflight_service.py tests/integration/test_restore_preflight_service.py` — passed.
