"""M2.4 restore preflight validation before pg_restore."""

from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from research_agent.application.backup_creation_service import DUMP_FILENAME, MANIFEST_FILENAME
from research_agent.application.migrations import run_migrations
from research_agent.application.restore_preflight_service import (
    RestorePreflightDenied,
    RestorePreflightService,
)
from research_agent.domain.backup import (
    BackupIntegrityMetadata,
    BackupManifest,
)
from research_agent.persistence.database import engine

SOURCE_REVISION = "316c90bf1816743ce73571e907b5c24e4da6cdec"
DUMP_BYTES = b"pg-dump-custom-bytes"


@pytest.fixture
def restore_target_db():
    schema = "restore_preflight_test_" + uuid4().hex
    with engine.begin() as conn:
        conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    isolated = create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        run_migrations(isolated)
        yield isolated
    finally:
        isolated.dispose()
        with engine.begin() as conn:
            conn.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')


def manifest_from_target(db) -> BackupManifest:
    from research_agent.application.backup_state_inspection_service import (
        BackupStateInspectionService,
    )

    inspection = BackupStateInspectionService(db).inspect(
        application_version="0.1.0",
        source_revision=SOURCE_REVISION,
    )
    dump_hash = sha256(DUMP_BYTES).hexdigest()
    return BackupManifest(
        backup_id=uuid4(),
        created_at=datetime(2026, 9, 25, tzinfo=UTC),
        database=inspection.database,
        application=inspection.application,
        schema_metadata=inspection.schema_metadata,
        authority=inspection.authority,
        integrity=BackupIntegrityMetadata(dump_sha256=dump_hash),
    )


def write_backup(tmp_path, manifest: BackupManifest, dump: bytes = DUMP_BYTES):
    backup = tmp_path / "backup-set"
    backup.mkdir()
    (backup / DUMP_FILENAME).write_bytes(dump)
    (backup / MANIFEST_FILENAME).write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return backup


def test_preflight_accepts_valid_backup_for_pristine_target(restore_target_db, tmp_path):
    manifest = manifest_from_target(restore_target_db)
    backup = write_backup(tmp_path, manifest)
    result = RestorePreflightService(restore_target_db).validate(backup)
    assert result.manifest == manifest
    assert result.dump_path == backup / DUMP_FILENAME


def test_hash_mismatch_is_rejected_before_restore(restore_target_db, tmp_path):
    backup = write_backup(tmp_path, manifest_from_target(restore_target_db), b"changed")
    with pytest.raises(RestorePreflightDenied, match="hash"):
        RestorePreflightService(restore_target_db).validate(backup)


def test_malformed_manifest_is_rejected(restore_target_db, tmp_path):
    backup = tmp_path / "backup-set"
    backup.mkdir()
    (backup / DUMP_FILENAME).write_bytes(DUMP_BYTES)
    (backup / MANIFEST_FILENAME).write_text('{"schema_version": 2}', encoding="utf-8")
    with pytest.raises(RestorePreflightDenied):
        RestorePreflightService(restore_target_db).validate(backup)


def test_future_postgresql_major_is_rejected(restore_target_db, tmp_path):
    manifest = manifest_from_target(restore_target_db)
    manifest = manifest.model_copy(
        update={
            "database": manifest.database.model_copy(
                update={"postgresql_major_version": 99}
            )
        }
    )
    backup = write_backup(tmp_path, manifest)
    with pytest.raises(RestorePreflightDenied, match="PostgreSQL"):
        RestorePreflightService(restore_target_db).validate(backup)


def test_newer_unsupported_schema_is_rejected(restore_target_db, tmp_path):
    manifest = manifest_from_target(restore_target_db)
    migration = manifest.schema_metadata.migrations[-1]
    manifest = manifest.model_copy(
        update={
            "schema_metadata": manifest.schema_metadata.model_copy(
                update={
                    "migrations": manifest.schema_metadata.migrations
                    + (
                        migration.model_copy(
                            update={
                                "version": migration.version + 1,
                                "name": f"{migration.version + 1:03d}_future.sql",
                            }
                        ),
                    )
                }
            )
        }
    )
    backup = write_backup(tmp_path, manifest)
    with pytest.raises(RestorePreflightDenied, match="schema"):
        RestorePreflightService(restore_target_db).validate(backup)


def test_altered_migration_checksum_is_rejected(restore_target_db, tmp_path):
    manifest = manifest_from_target(restore_target_db)
    first = manifest.schema_metadata.migrations[0]
    manifest = manifest.model_copy(
        update={
            "schema_metadata": manifest.schema_metadata.model_copy(
                update={
                    "migrations": (
                        first.model_copy(update={"checksum_sha256": "f" * 64}),
                    )
                    + manifest.schema_metadata.migrations[1:]
                }
            )
        }
    )
    backup = write_backup(tmp_path, manifest)
    with pytest.raises(RestorePreflightDenied, match="checksum"):
        RestorePreflightService(restore_target_db).validate(backup)


def test_populated_target_is_rejected(restore_target_db, tmp_path):
    manifest = manifest_from_target(restore_target_db)
    backup = write_backup(tmp_path, manifest)
    with restore_target_db.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO research_tasks (
                    id, title, objective, status, brief, plan, created_at, updated_at
                )
                VALUES (:id, 'Populated', 'Reject restore target.', 'active',
                        '{}'::jsonb, '{}'::jsonb, now(), now())
                """
            ),
            {"id": uuid4()},
        )
    with pytest.raises(RestorePreflightDenied, match="not pristine"):
        RestorePreflightService(restore_target_db).validate(backup)


def test_missing_dump_is_rejected(restore_target_db, tmp_path):
    backup = write_backup(tmp_path, manifest_from_target(restore_target_db))
    (backup / DUMP_FILENAME).unlink()
    with pytest.raises(RestorePreflightDenied, match="missing"):
        RestorePreflightService(restore_target_db).validate(backup)
