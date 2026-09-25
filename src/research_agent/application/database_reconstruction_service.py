"""M2.5 database reconstruction through a guarded pg_restore boundary."""

import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
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
            with TemporaryDirectory(prefix="gnomon-restore-") as directory:
                list_path = Path(directory) / "restore.list"
                self._write_restore_list(preflight.dump_path, list_path)
                args, env = self._pg_restore_command(preflight.dump_path, list_path)
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
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or "").strip()
            raise DatabaseReconstructionError(
                f"Database reconstruction failed: {detail or exc}"
            ) from exc
        except (
            BackupStateInspectionUnavailable,
            RestorePreflightDenied,
            OSError,
            SQLAlchemyError,
        ) as exc:
            raise DatabaseReconstructionError("Database reconstruction failed") from exc

    def _write_restore_list(self, dump_path: Path, list_path: Path) -> None:
        listing = self.runner(
            [self.pg_restore_path, "--list", str(dump_path)],
            env=self._restore_environment(),
            cwd=dump_path.parent,
        ).stdout
        if not listing:
            raise DatabaseReconstructionError("Backup archive has no restore listing")
        selected: list[str] = []
        table_positions: list[int] = []
        table_lines: dict[str, str] = {}
        for line in listing.splitlines(keepends=True):
            # pg_restore -L accepts its own -l output with entries commented out.
            fields = line.split(";", 1)
            if len(fields) == 2 and fields[0].strip().isdigit():
                parts = fields[1].split()
                if len(parts) >= 6 and parts[2:5] == ["TABLE", "DATA", "public"]:
                    table_name = parts[5]
                    if table_name in _RESTORE_EXCLUDED_TABLE_DATA:
                        line = ";" + line
                    else:
                        if table_name in table_lines:
                            raise DatabaseReconstructionError(
                                f"Duplicate table data in backup archive: {table_name}"
                            )
                        table_positions.append(len(selected))
                        table_lines[table_name] = line
            selected.append(line)
        remaining = dict(table_lines)
        parents: dict[str, set[str]] = {name: set() for name in remaining}
        for child, parent in self._table_dependencies():
            if child in parents and parent in parents and child != parent:
                parents[child].add(parent)
        ordered: list[str] = []
        while remaining:
            ready = next(
                (name for name in remaining if not parents[name].intersection(remaining)),
                None,
            )
            if ready is None:
                raise DatabaseReconstructionError(
                    "Backup tables have circular foreign-key dependencies"
                )
            ordered.append(remaining.pop(ready))
        for position, line in zip(table_positions, ordered, strict=True):
            selected[position] = line
        list_path.write_text("".join(selected), encoding="utf-8")

    def _table_dependencies(self) -> list[tuple[str, str]]:
        with self.target_engine.connect() as conn:
            return [
                (str(child), str(parent))
                for child, parent in conn.execute(
                    text(
                        """
                        SELECT child.relname, parent.relname
                        FROM pg_constraint AS fk
                        JOIN pg_class AS child ON child.oid = fk.conrelid
                        JOIN pg_namespace AS child_ns ON child_ns.oid = child.relnamespace
                        JOIN pg_class AS parent ON parent.oid = fk.confrelid
                        JOIN pg_namespace AS parent_ns ON parent_ns.oid = parent.relnamespace
                        WHERE fk.contype = 'f'
                          AND child_ns.nspname = current_schema()
                          AND parent_ns.nspname = current_schema()
                        """
                    )
                ).all()
            ]

    def _restore_environment(self) -> dict[str, str]:
        env = dict(self.environment)
        env.pop("DATABASE_URL", None)
        url = make_url(self.target_engine.url)
        if url.password:
            env["PGPASSWORD"] = url.password
        return env

    def _pg_restore_command(
        self, dump_path: Path, list_path: Path
    ) -> tuple[list[str], dict[str, str]]:
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
            "--use-list",
            str(list_path),
        ]
        if url.host:
            args.extend(["--host", url.host])
        if url.port:
            args.extend(["--port", str(url.port)])
        if url.username:
            args.extend(["--username", url.username])
        args.append(str(dump_path))
        return args, self._restore_environment()

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
