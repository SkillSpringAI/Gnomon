"""Read-only M2.2 backup state inspection."""

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from pydantic import ValidationError
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.orm import Session

from research_agent.application.migrations import MIGRATIONS_TABLE
from research_agent.application.security_state_store import (
    SecurityStateStore,
    SecurityStateUnavailable,
)
from research_agent.domain.backup import (
    BackupApplicationMetadata,
    BackupAuthorityMetadata,
    BackupDatabaseMetadata,
    BackupMigrationEntry,
    BackupSchemaMetadata,
)

SUPPORTED_POSTGRESQL_MAJOR_VERSIONS = frozenset({16})


class BackupStateInspectionUnavailable(RuntimeError):
    """The database cannot be described as a supported backup source."""


@dataclass(frozen=True)
class BackupStateInspection:
    """Manifest metadata available before a dump artifact exists."""

    database: BackupDatabaseMetadata
    application: BackupApplicationMetadata
    schema_metadata: BackupSchemaMetadata
    authority: BackupAuthorityMetadata


class BackupStateInspectionService:
    """Gather manifest metadata without mutating application state."""

    def __init__(
        self,
        engine: Engine,
        *,
        supported_postgresql_major_versions: Iterable[int] = SUPPORTED_POSTGRESQL_MAJOR_VERSIONS,
    ) -> None:
        self.engine = engine
        self.supported_postgresql_major_versions = frozenset(supported_postgresql_major_versions)

    @contextmanager
    def _transaction(self) -> Iterator[Session]:
        try:
            with self.engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
                with Session(bind=conn) as session, session.begin():
                    session.execute(text("SET TRANSACTION READ ONLY"))
                    yield session
        except BackupStateInspectionUnavailable:
            raise
        except DBAPIError as exc:
            raise BackupStateInspectionUnavailable("Backup state inspection failed") from exc

    def inspect(self, *, application_version: str, source_revision: str) -> BackupStateInspection:
        """Return the metadata needed to build a backup manifest later."""
        try:
            with self._transaction() as session:
                major = self._postgresql_major_version(session)
                if major not in self.supported_postgresql_major_versions:
                    raise BackupStateInspectionUnavailable(
                        "PostgreSQL major version is unsupported"
                    )
                current = SecurityStateStore(session).load()
                return BackupStateInspection(
                    database=BackupDatabaseMetadata(
                        postgresql_major_version=major,
                        database_scope=self._database_scope(session),
                    ),
                    application=BackupApplicationMetadata(
                        application_version=application_version,
                        source_revision=source_revision,
                    ),
                    schema_metadata=BackupSchemaMetadata(
                        migrations=tuple(self._migration_entries(session)),
                    ),
                    authority=BackupAuthorityMetadata(
                        authority_epoch_id=current.authority_epoch_id.value,
                        security_state=current.state,
                        security_state_version=current.version,
                        recovery_bootstrap_pending=current.recovery_bootstrap_pending,
                    ),
                )
        except (SecurityStateUnavailable, ValidationError, SQLAlchemyError) as exc:
            raise BackupStateInspectionUnavailable("Backup state is malformed") from exc

    @staticmethod
    def _postgresql_major_version(session: Session) -> int:
        raw = session.execute(text("SHOW server_version_num")).scalar_one()
        version_num = int(raw)
        return version_num // 10000 if version_num < 100000 else version_num // 10000

    @staticmethod
    def _database_scope(session: Session) -> str:
        return str(session.execute(text("SELECT current_database()")).scalar_one())

    @staticmethod
    def _migration_entries(session: Session) -> list[BackupMigrationEntry]:
        rows = session.execute(
            text(
                f"SELECT version, checksum FROM {MIGRATIONS_TABLE} "
                "ORDER BY version ASC"
            )
        ).all()
        if not rows:
            raise BackupStateInspectionUnavailable("Migration history is empty")
        entries: list[BackupMigrationEntry] = []
        for version_name, checksum in rows:
            if not isinstance(version_name, str) or len(version_name) < 4:
                raise BackupStateInspectionUnavailable("Migration version is malformed")
            try:
                version = int(version_name[:3])
            except ValueError as exc:
                raise BackupStateInspectionUnavailable("Migration version is malformed") from exc
            entries.append(
                BackupMigrationEntry(
                    version=version,
                    name=version_name,
                    checksum_sha256=checksum,
                )
            )
        return entries
