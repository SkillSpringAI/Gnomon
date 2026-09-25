"""M2.4 restore preflight validation before pg_restore."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from research_agent.application.backup_creation_service import DUMP_FILENAME, MANIFEST_FILENAME
from research_agent.application.backup_state_inspection_service import (
    BackupStateInspectionService,
    BackupStateInspectionUnavailable,
)
from research_agent.application.migrations import MIGRATIONS_TABLE
from research_agent.domain.backup import BackupManifest

_PRISTINE_ALLOWED_TABLES = frozenset({MIGRATIONS_TABLE, "security_state"})


class RestorePreflightDenied(RuntimeError):
    """Backup input or target database is not safe for reconstruction."""


@dataclass(frozen=True)
class RestorePreflightResult:
    backup_directory: Path
    dump_path: Path
    manifest_path: Path
    manifest: BackupManifest
    target_database_scope: str


class RestorePreflightService:
    """Validate backup material and target database before any pg_restore call."""

    def __init__(self, target_engine: Engine) -> None:
        self.target_engine = target_engine

    def validate(self, backup_directory: Path) -> RestorePreflightResult:
        root = Path(backup_directory)
        manifest_path = root / MANIFEST_FILENAME
        dump_path = root / DUMP_FILENAME
        try:
            manifest = BackupManifest.model_validate_json(
                manifest_path.read_text(encoding="utf-8")
            )
            if not dump_path.is_file():
                raise RestorePreflightDenied("Backup dump is missing")
            digest = sha256(dump_path.read_bytes()).hexdigest()
            if digest != manifest.integrity.dump_sha256:
                raise RestorePreflightDenied("Backup dump hash does not match manifest")
            target = BackupStateInspectionService(self.target_engine).inspect(
                application_version=manifest.application.application_version,
                source_revision=manifest.application.source_revision,
            )
            self._check_target_is_pristine()
            if (
                target.database.engine != manifest.database.engine
                or target.database.postgresql_major_version
                < manifest.database.postgresql_major_version
            ):
                raise RestorePreflightDenied("Target PostgreSQL version is incompatible")
            if target.schema_metadata.current_version < manifest.schema_metadata.current_version:
                raise RestorePreflightDenied("Target schema is older than the backup schema")
            known = {
                entry.version: entry.checksum_sha256
                for entry in target.schema_metadata.migrations
            }
            for entry in manifest.schema_metadata.migrations:
                if known.get(entry.version) != entry.checksum_sha256:
                    raise RestorePreflightDenied("Target migration checksums are incompatible")
            return RestorePreflightResult(
                backup_directory=root,
                dump_path=dump_path,
                manifest_path=manifest_path,
                manifest=manifest,
                target_database_scope=target.database.database_scope,
            )
        except RestorePreflightDenied:
            raise
        except (OSError, ValidationError, BackupStateInspectionUnavailable, SQLAlchemyError) as exc:
            raise RestorePreflightDenied("Restore preflight failed") from exc

    def _check_target_is_pristine(self) -> None:
        with self.target_engine.connect().execution_options(
            isolation_level="REPEATABLE READ"
        ) as conn:
            with conn.begin():
                rows = conn.execute(
                    text(
                        """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = current_schema()
                          AND table_type = 'BASE TABLE'
                        """
                    )
                ).all()
                populated: list[str] = []
                for (table_name,) in rows:
                    if table_name in _PRISTINE_ALLOWED_TABLES:
                        continue
                    count: int = int(
                        conn.execute(
                            text(f'SELECT count(*) FROM "{table_name}"')
                        ).scalar_one()
                    )
                    if count > 0:
                        populated.append(str(table_name))
                if populated:
                    raise RestorePreflightDenied("Target database is not pristine")
