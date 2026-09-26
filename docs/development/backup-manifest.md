# Backup Manifest — M2.1

> Dated execution and verification record. Status and remaining-work statements below describe this checkpoint; use the maintained [current source of truth](source-of-truth.md) and [roadmap](roadmap.md) for present claims.

Date: 25 September 2026.
Status: domain contract implemented locally.

## Scope

M2.1 adds immutable manifest metadata only. It does not invoke `pg_dump`, read a
database, inspect migrations from runtime state, publish backup files or authorize
restore.

The contract lives in `src/research_agent/domain/backup.py` and defines:

- `BackupManifest`;
- `BackupDatabaseMetadata`;
- `BackupApplicationMetadata`;
- `BackupSchemaMetadata`;
- `BackupMigrationEntry`;
- `BackupAuthorityMetadata`;
- `BackupIntegrityMetadata`.

## Semantics

The manifest is fixed to schema version 1 and records:

- non-nil backup identity;
- UTC creation timestamp;
- PostgreSQL database metadata;
- application version and source revision;
- strictly ordered migration entries with SHA-256 checksums;
- current authority epoch, security state and security-state version;
- dump format and SHA-256 digest.

All manifest objects are frozen and reject extra fields. The manifest is metadata
and does not grant authority after restore.

## Limits

PostgreSQL state inspection, dump creation, restore preflight, reconstruction,
credential sentinel verification and epoch rotation after reconstruction remain M2
work.

## Verification

Local M2.1 verification:

- `python -m pytest tests/unit/test_backup_manifest_contract.py` — 28 passed.
- `python -m ruff check src/research_agent/domain/backup.py tests/unit/test_backup_manifest_contract.py` — passed.
- `python -m mypy src` — passed across 97 source files.
- `git diff --check` — passed.
