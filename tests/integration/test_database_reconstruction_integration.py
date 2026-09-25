"""M2.5 database reconstruction service behavior before recovery startup."""

import shutil
from datetime import UTC, datetime
from hashlib import sha256
from subprocess import CalledProcessError, CompletedProcess
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from research_agent.application.backup_creation_service import (
    DUMP_FILENAME,
    MANIFEST_FILENAME,
    BackupCreationService,
)
from research_agent.application.backup_state_inspection_service import (
    BackupStateInspectionService,
)
from research_agent.application.database_reconstruction_service import (
    DatabaseReconstructionError,
    DatabaseReconstructionService,
)
from research_agent.application.migrations import run_migrations
from research_agent.config.settings import get_settings
from research_agent.domain.backup import BackupIntegrityMetadata, BackupManifest
from research_agent.persistence.database import engine

SOURCE_REVISION = "316c90bf1816743ce73571e907b5c24e4da6cdec"
DUMP_BYTES = b"pg-restore-custom-bytes"
TEST_ARCHIVE_LISTING = "3; 0 103 TABLE DATA public research_tasks owner\n"


@pytest.fixture
def reconstruction_target_db():
    schema = "database_reconstruction_test_" + uuid4().hex
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
    inspection = BackupStateInspectionService(db).inspect(
        application_version="0.1.0",
        source_revision=SOURCE_REVISION,
    )
    return BackupManifest(
        backup_id=uuid4(),
        created_at=datetime(2026, 9, 25, tzinfo=UTC),
        database=inspection.database,
        application=inspection.application,
        schema_metadata=inspection.schema_metadata,
        authority=inspection.authority,
        integrity=BackupIntegrityMetadata(dump_sha256=sha256(DUMP_BYTES).hexdigest()),
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


def test_reconstruction_runs_restore_and_verifies_target(
    reconstruction_target_db, tmp_path
):
    manifest = manifest_from_target(reconstruction_target_db)
    backup = write_backup(tmp_path, manifest)
    task_id = uuid4()

    def runner(args, *, env, cwd=None):
        if "--list" in args:
            return CompletedProcess(args, 0, TEST_ARCHIVE_LISTING, "")
        assert "--data-only" in args
        assert "--single-transaction" in args
        assert "--use-list" in args
        assert cwd == backup
        with reconstruction_target_db.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO research_tasks (
                        id, title, objective, status, brief, plan, created_at, updated_at
                    )
                    VALUES (:id, 'Reconstructed', 'Verify reconstruction.', 'active',
                            '{}'::jsonb, '{}'::jsonb, now(), now())
                    """
                ),
                {"id": task_id},
            )

    result = DatabaseReconstructionService(
        reconstruction_target_db,
        runner=runner,
        environment={"PATH": "test"},
    ).reconstruct(backup)

    assert result.applied_migrations == ()
    with reconstruction_target_db.connect() as conn:
        assert conn.scalar(
            text("SELECT title FROM research_tasks WHERE id = :id"), {"id": task_id}
        ) == "Reconstructed"
        restored = conn.execute(
            text(
                """
                SELECT state, version, authority_epoch_id, recovery_bootstrap_pending
                FROM security_state WHERE id = 1
                """
            )
        ).one()
    assert restored.state == manifest.authority.security_state.value
    assert restored.version == manifest.authority.security_state_version
    assert restored.authority_epoch_id == manifest.authority.authority_epoch_id
    assert restored.recovery_bootstrap_pending is manifest.authority.recovery_bootstrap_pending


def test_failed_pg_restore_surfaces_without_rewriting_authority(
    reconstruction_target_db, tmp_path
):
    backup = write_backup(tmp_path, manifest_from_target(reconstruction_target_db))
    with reconstruction_target_db.connect() as conn:
        before = conn.scalar(text("SELECT to_jsonb(s) FROM security_state s"))

    def runner(args, *, env, cwd=None):
        if "--list" in args:
            return CompletedProcess(args, 0, TEST_ARCHIVE_LISTING, "")
        raise CalledProcessError(1, args, stderr="pg_restore: error: COPY research_tasks failed")

    with pytest.raises(DatabaseReconstructionError, match="COPY research_tasks failed"):
        DatabaseReconstructionService(
            reconstruction_target_db,
            runner=runner,
        ).reconstruct(backup)

    with reconstruction_target_db.connect() as conn:
        assert conn.scalar(text("SELECT to_jsonb(s) FROM security_state s")) == before


def test_reconstruction_rejects_malformed_restored_authority(
    reconstruction_target_db, tmp_path
):
    manifest = manifest_from_target(reconstruction_target_db)
    backup = write_backup(tmp_path, manifest)

    def runner(args, *, env, cwd=None):
        if "--list" in args:
            return CompletedProcess(args, 0, TEST_ARCHIVE_LISTING, "")
        with reconstruction_target_db.begin() as conn:
            conn.execute(text("DELETE FROM security_state"))

    with pytest.raises(DatabaseReconstructionError):
        DatabaseReconstructionService(
            reconstruction_target_db,
            runner=runner,
        ).reconstruct(backup)


@pytest.mark.skipif(
    shutil.which("pg_dump") is None or shutil.which("pg_restore") is None,
    reason="pg_dump and pg_restore are not installed",
)
def test_real_pg_restore_reconstructs_task_data(tmp_path):
    base_url = make_url(get_settings().database_url)
    if base_url.host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("real reconstruction integration requires local PostgreSQL")
    source_database = "database_reconstruction_source_" + uuid4().hex
    target_database = "database_reconstruction_target_" + uuid4().hex
    admin = create_engine(base_url, isolation_level="AUTOCOMMIT")
    created: list[str] = []
    source = create_engine(base_url.set(database=source_database))
    target = create_engine(base_url.set(database=target_database))
    task_id = uuid4()
    try:
        try:
            with admin.connect() as conn:
                conn.exec_driver_sql(f'CREATE DATABASE "{source_database}"')
                created.append(source_database)
                conn.exec_driver_sql(f'CREATE DATABASE "{target_database}"')
                created.append(target_database)
        except SQLAlchemyError as exc:
            pytest.skip(f"cannot create disposable databases: {exc}")
        run_migrations(source)
        run_migrations(target)
        with source.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO research_tasks (
                        id, title, objective, status, brief, plan, created_at, updated_at
                    )
                    VALUES (:id, 'Real restore', 'Verify pg_restore.', 'active',
                            '{}'::jsonb, '{}'::jsonb, now(), now())
                    """
                ),
                {"id": task_id},
            )
        backup = BackupCreationService(source).create(
            tmp_path / "backup-set",
            application_version="0.1.0",
            source_revision=SOURCE_REVISION,
        )
        DatabaseReconstructionService(target).reconstruct(backup.backup_directory)
        with target.connect() as conn:
            assert conn.scalar(
                text("SELECT title FROM research_tasks WHERE id = :id"),
                {"id": task_id},
            ) == "Real restore"
    finally:
        source.dispose()
        target.dispose()
        for database in reversed(created):
            with admin.connect() as conn:
                conn.exec_driver_sql(f'DROP DATABASE "{database}" WITH (FORCE)')
        admin.dispose()
