"""M2.3 backup creation publishes only complete dump and manifest sets."""

import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine

from research_agent.application.backup_creation_service import (
    DUMP_FILENAME,
    MANIFEST_FILENAME,
    BackupCreationError,
    BackupCreationService,
)
from research_agent.application.backup_state_inspection_service import BackupStateInspection
from research_agent.domain.backup import (
    BackupApplicationMetadata,
    BackupAuthorityMetadata,
    BackupDatabaseMetadata,
    BackupManifest,
    BackupMigrationEntry,
    BackupSchemaMetadata,
)
from research_agent.domain.security import SecurityState

SOURCE_REVISION = "316c90bf1816743ce73571e907b5c24e4da6cdec"


def engine():
    return create_engine(
        "postgresql+psycopg://research_agent:secret@localhost:5432/research_agent"
    )


class Inspector:
    def __init__(self, *, source_revision: str = SOURCE_REVISION) -> None:
        self.source_revision = source_revision

    def inspect(self, *, application_version: str, source_revision: str) -> BackupStateInspection:
        return BackupStateInspection(
            database=BackupDatabaseMetadata(
                postgresql_major_version=16,
                database_scope="research_agent",
            ),
            application=BackupApplicationMetadata(
                application_version=application_version,
                source_revision=self.source_revision if source_revision else source_revision,
            ),
            schema_metadata=BackupSchemaMetadata(
                migrations=(
                    BackupMigrationEntry(
                        version=1,
                        name="001_initial.sql",
                        checksum_sha256="a" * 64,
                    ),
                )
            ),
            authority=BackupAuthorityMetadata(
                authority_epoch_id=uuid4(),
                security_state=SecurityState.NORMAL,
                security_state_version=1,
            ),
        )


def fake_runner(args, *, env, cwd: Path | None = None):
    assert cwd is not None
    assert "secret" not in args
    assert "DATABASE_URL" not in env
    assert env["PGPASSWORD"] == "secret"
    assert "--format=custom" in args
    dump_path = Path(args[args.index("--file") + 1])
    dump_path.write_bytes(b"pg-dump-custom-bytes")
    return subprocess.CompletedProcess(args=list(args), returncode=0)


def test_backup_creation_publishes_manifest_and_dump(tmp_path):
    backup_id = uuid4()
    result = BackupCreationService(
        engine(),
        pg_dump_path="pg_dump-test",
        runner=fake_runner,
        environment={"PATH": "test", "DATABASE_URL": "postgresql://user:secret@example/db"},
        state_inspector=Inspector(),
    ).create(
        tmp_path / "backup-set",
        application_version="0.1.0",
        source_revision=SOURCE_REVISION,
        backup_id=backup_id,
    )
    assert result.backup_id == backup_id
    assert result.dump_path.read_bytes() == b"pg-dump-custom-bytes"
    assert result.manifest_path.is_file()
    assert not list(tmp_path.glob(".backup-set.tmp-*"))
    manifest = BackupManifest.model_validate_json(result.manifest_path.read_text())
    assert manifest == result.manifest
    assert manifest.backup_id == backup_id
    assert manifest.integrity.dump_sha256
    assert "secret" not in result.manifest_path.read_text()


def test_existing_destination_is_rejected_without_running_pg_dump(tmp_path):
    destination = tmp_path / "backup-set"
    destination.mkdir()
    calls = []

    def runner(args, *, env, cwd=None):
        calls.append(args)
        return subprocess.CompletedProcess(args=list(args), returncode=0)

    with pytest.raises(BackupCreationError, match="already exists"):
        BackupCreationService(engine(), runner=runner, state_inspector=Inspector()).create(
            destination,
            application_version="0.1.0",
            source_revision=SOURCE_REVISION,
        )
    assert calls == []
    assert list(destination.iterdir()) == []


def test_pg_dump_failure_publishes_nothing(tmp_path):
    def failing_runner(args, *, env, cwd=None):
        raise subprocess.CalledProcessError(1, args)

    destination = tmp_path / "backup-set"
    with pytest.raises(BackupCreationError):
        BackupCreationService(
            engine(), runner=failing_runner, state_inspector=Inspector()
        ).create(
            destination,
            application_version="0.1.0",
            source_revision=SOURCE_REVISION,
        )
    assert not destination.exists()
    assert not list(tmp_path.glob(".backup-set.tmp-*"))


def test_missing_dump_file_publishes_nothing(tmp_path):
    def no_output_runner(args, *, env, cwd=None):
        return subprocess.CompletedProcess(args=list(args), returncode=0)

    destination = tmp_path / "backup-set"
    with pytest.raises(BackupCreationError):
        BackupCreationService(
            engine(), runner=no_output_runner, state_inspector=Inspector()
        ).create(
            destination,
            application_version="0.1.0",
            source_revision=SOURCE_REVISION,
        )
    assert not destination.exists()


def test_malformed_source_state_publishes_nothing(tmp_path):
    destination = tmp_path / "backup-set"
    with pytest.raises(BackupCreationError):
        BackupCreationService(engine(), state_inspector=Inspector(source_revision="bad")).create(
            destination,
            application_version="0.1.0",
            source_revision="bad revision",
        )
    assert not destination.exists()


def test_dump_filename_constants_are_stable():
    assert DUMP_FILENAME == "database.dump"
    assert MANIFEST_FILENAME == "manifest.json"
