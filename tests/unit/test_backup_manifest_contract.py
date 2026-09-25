"""M2.1 backup manifest is bounded metadata, not restore authority."""

from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from research_agent.domain.backup import BackupManifest

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


@pytest.fixture
def manifest_payload():
    return {
        "backup_id": uuid4(),
        "created_at": datetime(2026, 9, 24, 12, tzinfo=UTC),
        "database": {
            "engine": "postgresql",
            "postgresql_major_version": 16,
            "database_scope": "research_agent",
        },
        "application": {
            "application_name": "research-agent",
            "application_version": "0.1.0",
            "source_revision": "316c90bf1816743ce73571e907b5c24e4da6cdec",
        },
        "schema_metadata": {
            "migrations": [
                {"version": 1, "name": "001_initial.sql", "checksum_sha256": SHA_A},
                {"version": 2, "name": "002_evidence.sql", "checksum_sha256": SHA_B},
            ],
        },
        "authority": {
            "authority_epoch_id": uuid4(),
            "security_state": "normal",
            "security_state_version": 9,
            "recovery_bootstrap_pending": False,
        },
        "integrity": {
            "dump_format": "pg_dump_custom",
            "dump_sha256": SHA_C,
        },
    }


def test_manifest_roundtrip_is_immutable_and_deterministic(manifest_payload):
    manifest = BackupManifest.model_validate(manifest_payload)
    assert BackupManifest.model_validate_json(manifest.model_dump_json()) == manifest
    assert manifest.schema_metadata.current_version == 2
    manifest_payload["schema_metadata"]["migrations"].clear()
    assert len(manifest.schema_metadata.migrations) == 2
    with pytest.raises(ValidationError):
        manifest.backup_id = uuid4()
    with pytest.raises(ValidationError):
        manifest.schema_metadata.migrations[0].version = 99


@pytest.mark.parametrize(
    "path,value",
    [
        (("backup_id",), UUID(int=0)),
        (("created_at",), datetime(2026, 9, 24, 12)),
        (("created_at",), datetime(2026, 9, 24, 12, tzinfo=timezone(timedelta(hours=12)))),
        (("database", "engine"), "sqlite"),
        (("database", "postgresql_major_version"), 0),
        (("database", "postgresql_major_version"), "16"),
        (("database", "database_scope"), " "),
        (("application", "application_name"), "gnomon"),
        (("application", "application_version"), ""),
        (("application", "source_revision"), "not-a-revision"),
        (("schema_metadata", "migrations"), []),
        (("schema_metadata", "migrations", 0, "version"), 0),
        (("schema_metadata", "migrations", 0, "name"), "999_initial.sql"),
        (("schema_metadata", "migrations", 0, "checksum_sha256"), "A" * 64),
        (("schema_metadata", "migrations", 0, "checksum_sha256"), "a" * 63),
        (("authority", "authority_epoch_id"), UUID(int=0)),
        (("authority", "security_state"), "restored"),
        (("authority", "security_state_version"), 0),
        (("authority", "recovery_bootstrap_pending"), "false"),
        (("integrity", "dump_format"), "plain_sql"),
        (("integrity", "dump_sha256"), "c" * 63),
        (("schema_version",), 2),
    ],
)
def test_malformed_manifest_fields_are_rejected(manifest_payload, path, value):
    target = manifest_payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        BackupManifest.model_validate(manifest_payload)


def test_migration_history_must_be_strictly_ordered(manifest_payload):
    migrations = manifest_payload["schema_metadata"]["migrations"]
    migrations.reverse()
    with pytest.raises(ValidationError, match="ordered"):
        BackupManifest.model_validate(manifest_payload)
    migrations.reverse()
    migrations.append({"version": 2, "name": "002_duplicate.sql", "checksum_sha256": SHA_C})
    with pytest.raises(ValidationError, match="ordered"):
        BackupManifest.model_validate(manifest_payload)


@pytest.mark.parametrize(
    "path,key,value",
    [
        ((), "operator_authorization", str(uuid4())),
        (("authority",), "execution_authorization_id", str(uuid4())),
        (("integrity",), "database_password", "secret"),
        (("database",), "credential", "secret"),
    ],
)
def test_extra_authority_or_credential_fields_are_rejected(manifest_payload, path, key, value):
    target = manifest_payload
    for item in path:
        target = target[item]
    target[key] = value
    with pytest.raises(ValidationError):
        BackupManifest.model_validate(manifest_payload)
