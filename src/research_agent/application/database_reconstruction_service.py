"""M2.5 database reconstruction through a guarded pg_restore boundary."""

import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from sqlalchemy import Engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from research_agent.application.backup_creation_service import ProcessRunner, _default_runner
from research_agent.application.backup_state_inspection_service import (
    BackupStateInspectionService,
    BackupStateInspectionUnavailable,
)
from research_agent.application.migrations import MIGRATIONS_TABLE, run_migrations
from research_agent.application.restore_preflight_service import (
    RestorePreflightDenied,
    RestorePreflightResult,
    RestorePreflightService,
)

_RESTORE_EXCLUDED_TABLE_DATA = frozenset({MIGRATIONS_TABLE, "security_state"})
_CRITICAL_TABLES = (MIGRATIONS_TABLE, "security_state", "research_tasks")


class DatabaseReconstructionError(RuntimeError):
    """Database reconstruction did not complete a verified import."""


class RestorePreflightValidator(Protocol):
    def validate(self, backup_directory: Path) -> RestorePreflightResult:
        """Return validated restore material and target compatibility metadata."""


@dataclass(frozen=True)
class DatabaseReconstructionResult:
    backup_directory: Path
    dump_path: Path
    applied_migrations: tuple[str, ...]
    target_database_scope: str


class DatabaseReconstructionService:
    """Restore backup data into a preflighted pristine PostgreSQL target."""

    def __init__(
        self,
        target_engine: Engine,
        *,
        pg_restore_path: str = "pg_restore",
        runner: ProcessRunner = _default_runner,
        environment: Mapping[str, str] | None = None,
        preflight: RestorePreflightValidator | None = None,
    ) -> None:
        self.target_engine = target_engine
        self.pg_restore_path = pg_restore_path
        self.runner = runner
        self.environment = dict(environment if environment is not None else os.environ)
        self.preflight = preflight

    def reconstruct(self, backup_directory: Path) -> DatabaseReconstructionResult:
        try:
            preflight = (self.preflight or RestorePreflightService(self.target_engine)).validate(
                Path(backup_directory)
            )
            args, env = self._pg_restore_command(preflight.dump_path)
            self.runner(args, env=env, cwd=preflight.backup_directory)
            self._apply_restored_authority(preflight)
            applied = tuple(run_migrations(self.target_engine))
            inspection = BackupStateInspectionService(self.target_engine).inspect(
                application_version=preflight.manifest.application.application_version,
                source_revision=preflight.manifest.application.source_revision,
            )
            if inspection.authority != preflight.manifest.authority:
                raise DatabaseReconstructionError("Restored authority metadata mismatch")
            self._verify_critical_tables()
            return DatabaseReconstructionResult(
                backup_directory=preflight.backup_directory,
                dump_path=preflight.dump_path,
                applied_migrations=applied,
                target_database_scope=inspection.database.database_scope,
            )
        except DatabaseReconstructionError:
            raise
        except (
            BackupStateInspectionUnavailable,
            RestorePreflightDenied,
            OSError,
            SQLAlchemyError,
            subprocess.CalledProcessError,
        ) as exc:
            raise DatabaseReconstructionError("Database reconstruction failed") from exc

    def _pg_restore_command(self, dump_path: Path) -> tuple[list[str], dict[str, str]]:
        url = make_url(self.target_engine.url)
        if not url.drivername.startswith("postgresql"):
            raise DatabaseReconstructionError("Only PostgreSQL database URLs are supported")
        if not url.database:
            raise DatabaseReconstructionError("Database URL must name a database")
        args = [
            self.pg_restore_path,
            "--data-only",
            "--single-transaction",
            "--exit-on-error",
            "--no-owner",
            "--no-privileges",
            "--dbname",
            url.database,
            "--no-password",
        ]
        for table_name in sorted(_RESTORE_EXCLUDED_TABLE_DATA):
            args.append(f"--exclude-table-data={table_name}")
        if url.host:
            args.extend(["--host", url.host])
        if url.port:
            args.extend(["--port", str(url.port)])
        if url.username:
            args.extend(["--username", url.username])
        args.append(str(dump_path))
        env = dict(self.environment)
        env.pop("DATABASE_URL", None)
        if url.password:
            env["PGPASSWORD"] = url.password
        return args, env

    def _apply_restored_authority(self, preflight: RestorePreflightResult) -> None:
        authority = preflight.manifest.authority
        with self.target_engine.begin() as conn:
            updated = conn.execute(
                text(
                    """
                    UPDATE security_state
                    SET state = :state,
                        version = :version,
                        authority_epoch_id = :authority_epoch_id,
                        recovery_bootstrap_pending = :recovery_bootstrap_pending,
                        recovery_bootstrap_started_at = NULL,
                        recovery_bootstrap_from_state = NULL,
                        recovery_bootstrap_from_version = NULL,
                        updated_at = now()
                    WHERE id = 1
                    """
                ),
                {
                    "state": authority.security_state.value,
                    "version": authority.security_state_version,
                    "authority_epoch_id": authority.authority_epoch_id,
                    "recovery_bootstrap_pending": authority.recovery_bootstrap_pending,
                },
            )
            if updated.rowcount != 1:
                raise DatabaseReconstructionError("Canonical security state is missing")

    def _verify_critical_tables(self) -> None:
        with self.target_engine.connect() as conn:
            for table_name in _CRITICAL_TABLES:
                conn.execute(text(f'SELECT 1 FROM "{table_name}" LIMIT 1')).all()
