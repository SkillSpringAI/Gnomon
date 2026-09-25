"""M2 backup manifest contracts; metadata only, no backup execution."""

from datetime import timedelta
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from research_agent.domain.security import SecurityState


def _non_nil(value: UUID) -> UUID:
    if value.int == 0:
        raise ValueError("Backup identifiers must not be nil")
    return value


BackupId = Annotated[UUID, AfterValidator(_non_nil)]
StateVersion = Annotated[int, Field(strict=True, ge=1)]
PostgreSQLMajorVersion = Annotated[int, Field(strict=True, ge=12, le=99)]
Sha256Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
SourceRevision = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{7,64}$")]
MigrationName = Annotated[str, Field(strict=True, min_length=8, max_length=128)]


class BackupValue(BaseModel):
    """Frozen manifest values prevent accidental mutation after validation."""

    model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="always")


class BackupMigrationEntry(BackupValue):
    """A migration identity as represented in the backed-up database."""

    version: StateVersion
    name: MigrationName
    checksum_sha256: Sha256Digest

    @model_validator(mode="after")
    def name_matches_version(self) -> Self:
        prefix = f"{self.version:03d}_"
        if not self.name.startswith(prefix) or not self.name.endswith(".sql"):
            raise ValueError("Migration name must match its numbered version")
        return self


class BackupDatabaseMetadata(BackupValue):
    """Database engine metadata required before restore compatibility checks."""

    engine: Literal["postgresql"] = "postgresql"
    postgresql_major_version: PostgreSQLMajorVersion
    database_scope: Annotated[str, Field(strict=True, min_length=1, max_length=120)]

    @model_validator(mode="after")
    def bounded_scope(self) -> Self:
        if not self.database_scope.strip():
            raise ValueError("Database scope must not be blank")
        return self


class BackupApplicationMetadata(BackupValue):
    """Application build metadata captured alongside the database dump."""

    application_name: Literal["research-agent"] = "research-agent"
    application_version: Annotated[str, Field(strict=True, min_length=1, max_length=80)]
    source_revision: SourceRevision


class BackupSchemaMetadata(BackupValue):
    """Ordered migration history in the source database."""

    migrations: tuple[BackupMigrationEntry, ...] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def migrations_are_ordered(self) -> Self:
        versions = [entry.version for entry in self.migrations]
        if versions != sorted(versions) or len(set(versions)) != len(versions):
            raise ValueError("Migration entries must be strictly ordered by version")
        return self

    @property
    def current_version(self) -> int:
        return self.migrations[-1].version


class BackupAuthorityMetadata(BackupValue):
    """Authority snapshot metadata; this grants no authority after restore."""

    authority_epoch_id: BackupId
    security_state: SecurityState
    security_state_version: StateVersion
    recovery_bootstrap_pending: Annotated[bool, Field(strict=True)] = False


class BackupIntegrityMetadata(BackupValue):
    """Integrity data for the dump artifact referenced by the manifest."""

    dump_format: Literal["pg_dump_custom"] = "pg_dump_custom"
    dump_sha256: Sha256Digest


class BackupManifest(BackupValue):
    """Canonical v1 metadata for one PostgreSQL backup artifact."""

    schema_version: Literal[1] = 1
    backup_id: BackupId
    created_at: AwareDatetime
    database: BackupDatabaseMetadata
    application: BackupApplicationMetadata
    schema_metadata: BackupSchemaMetadata
    authority: BackupAuthorityMetadata
    integrity: BackupIntegrityMetadata

    @model_validator(mode="after")
    def manifest_is_bounded(self) -> Self:
        if self.created_at.utcoffset() != timedelta(0):
            raise ValueError("Backup manifest timestamp must be UTC")
        return self
