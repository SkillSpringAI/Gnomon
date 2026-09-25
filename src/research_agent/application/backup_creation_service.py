"""Trusted M2.3 PostgreSQL backup creation boundary."""

import os
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.engine import make_url

from research_agent.application.backup_state_inspection_service import (
    BackupStateInspection,
    BackupStateInspectionService,
    BackupStateInspectionUnavailable,
)
from research_agent.domain.backup import BackupIntegrityMetadata, BackupManifest

DUMP_FILENAME = "database.dump"
MANIFEST_FILENAME = "manifest.json"


class BackupCreationError(RuntimeError):
    """Backup creation did not publish a complete backup set."""


class ProcessRunner(Protocol):
    def __call__(
        self,
        args: Sequence[str],
        *,
        env: Mapping[str, str],
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run a process and raise on failure."""


class BackupStateInspector(Protocol):
    def inspect(self, *, application_version: str, source_revision: str) -> BackupStateInspection:
        """Return source-state metadata for manifest construction."""


def _default_runner(
    args: Sequence[str],
    *,
    env: Mapping[str, str],
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        check=True,
        cwd=cwd,
        env=dict(env),
        text=True,
        capture_output=True,
    )


@dataclass(frozen=True)
class BackupCreationResult:
    backup_id: UUID
    backup_directory: Path
    dump_path: Path
    manifest_path: Path
    manifest: BackupManifest


class BackupCreationService:
    """Create one complete dump plus manifest set, or publish nothing."""

    def __init__(
        self,
        engine: Engine,
        *,
        pg_dump_path: str = "pg_dump",
        runner: ProcessRunner = _default_runner,
        environment: Mapping[str, str] | None = None,
        state_inspector: BackupStateInspector | None = None,
    ) -> None:
        self.engine = engine
        self.pg_dump_path = pg_dump_path
        self.runner = runner
        self.environment = dict(environment if environment is not None else os.environ)
        self.state_inspector = state_inspector

    def create(
        self,
        backup_directory: Path,
        *,
        application_version: str,
        source_revision: str,
        backup_id: UUID | None = None,
    ) -> BackupCreationResult:
        backup_id = backup_id or uuid4()
        target = Path(backup_directory)
        if target.exists():
            raise BackupCreationError("Backup destination already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.parent / f".{target.name}.tmp-{uuid4().hex}"
        try:
            temp.mkdir()
            inspector = self.state_inspector or BackupStateInspectionService(self.engine)
            inspection = inspector.inspect(
                application_version=application_version,
                source_revision=source_revision,
            )
            dump_path = temp / DUMP_FILENAME
            args, env = self._pg_dump_command(dump_path)
            self.runner(args, env=env, cwd=temp)
            if not dump_path.is_file():
                raise BackupCreationError("pg_dump did not create the expected dump file")
            digest = sha256(dump_path.read_bytes()).hexdigest()
            manifest = BackupManifest(
                backup_id=backup_id,
                created_at=datetime.now(UTC),
                database=inspection.database,
                application=inspection.application,
                schema_metadata=inspection.schema_metadata,
                authority=inspection.authority,
                integrity=BackupIntegrityMetadata(dump_sha256=digest),
            )
            manifest_path = temp / MANIFEST_FILENAME
            manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
            temp.rename(target)
            return BackupCreationResult(
                backup_id=backup_id,
                backup_directory=target,
                dump_path=target / DUMP_FILENAME,
                manifest_path=target / MANIFEST_FILENAME,
                manifest=manifest,
            )
        except (
            BackupCreationError,
            BackupStateInspectionUnavailable,
            OSError,
            ValidationError,
            subprocess.CalledProcessError,
        ) as exc:
            shutil.rmtree(temp, ignore_errors=True)
            raise BackupCreationError("Backup creation failed") from exc
        except Exception:
            shutil.rmtree(temp, ignore_errors=True)
            raise

    def _pg_dump_command(self, dump_path: Path) -> tuple[list[str], dict[str, str]]:
        url = make_url(self.engine.url)
        if not url.drivername.startswith("postgresql"):
            raise BackupCreationError("Only PostgreSQL database URLs are supported")
        if not url.database:
            raise BackupCreationError("Database URL must name a database")
        args = [
            self.pg_dump_path,
            "--format=custom",
            "--file",
            str(dump_path),
            "--dbname",
            url.database,
            "--no-password",
        ]
        if url.host:
            args.extend(["--host", url.host])
        if url.port:
            args.extend(["--port", str(url.port)])
        if url.username:
            args.extend(["--username", url.username])
        env = dict(self.environment)
        env.pop("DATABASE_URL", None)
        if url.password:
            env["PGPASSWORD"] = url.password
        return args, env
