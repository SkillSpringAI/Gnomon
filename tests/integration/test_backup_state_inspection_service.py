"""M2.2 read-only backup source-state inspection."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text

from research_agent.application.backup_state_inspection_service import (
    BackupStateInspectionService,
    BackupStateInspectionUnavailable,
)
from research_agent.application.migrations import MIGRATIONS_TABLE, run_migrations
from research_agent.domain.security import SecurityState
from research_agent.persistence.database import engine

SOURCE_REVISION = "316c90bf1816743ce73571e907b5c24e4da6cdec"


@pytest.fixture
def backup_inspection_db():
    schema = "backup_state_test_" + uuid4().hex
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


def inspect(db, **kwargs):
    return BackupStateInspectionService(db, **kwargs).inspect(
        application_version="0.1.0",
        source_revision=SOURCE_REVISION,
    )


def test_inspection_describes_valid_populated_database_without_mutation(backup_inspection_db):
    with backup_inspection_db.begin() as conn:
        before_state = conn.scalar(text("SELECT to_jsonb(s) FROM security_state s"))
        migration_count = conn.scalar(text(f"SELECT count(*) FROM {MIGRATIONS_TABLE}"))
        conn.execute(
            text(
                """
                INSERT INTO research_tasks (
                    id, title, objective, status, brief, plan, created_at, updated_at
                )
                VALUES (:id, 'Backup fixture', 'Exercise inspection', 'active',
                        '{}'::jsonb, '{}'::jsonb, now(), now())
                """
            ),
            {"id": uuid4()},
        )
    result = inspect(backup_inspection_db)
    assert result.database.engine == "postgresql"
    assert result.database.postgresql_major_version == 16
    assert result.application.source_revision == SOURCE_REVISION
    assert result.schema_metadata.current_version == migration_count
    assert result.authority.security_state is SecurityState.NORMAL
    assert result.authority.security_state_version == 1
    assert result.authority.authority_epoch_id.int != 0
    with backup_inspection_db.begin() as conn:
        assert conn.scalar(text("SELECT to_jsonb(s) FROM security_state s")) == before_state
        assert conn.scalar(text(f"SELECT count(*) FROM {MIGRATIONS_TABLE}")) == migration_count


def test_missing_migration_table_fails_closed(backup_inspection_db):
    with backup_inspection_db.begin() as conn:
        conn.execute(text(f"DROP TABLE {MIGRATIONS_TABLE}"))
    with pytest.raises(BackupStateInspectionUnavailable):
        inspect(backup_inspection_db)


@pytest.mark.parametrize(
    "statement",
    [
        f"UPDATE {MIGRATIONS_TABLE} SET checksum = 'not-a-sha' WHERE version = '001_initial.sql'",
        f"UPDATE {MIGRATIONS_TABLE} SET version = 'bad.sql' WHERE version = '001_initial.sql'",
        f"DELETE FROM {MIGRATIONS_TABLE}",
    ],
)
def test_malformed_migration_history_fails_closed(backup_inspection_db, statement):
    with backup_inspection_db.begin() as conn:
        conn.execute(text(statement))
    with pytest.raises(BackupStateInspectionUnavailable):
        inspect(backup_inspection_db)


def test_missing_security_state_fails_closed(backup_inspection_db):
    with backup_inspection_db.begin() as conn:
        conn.execute(text("DELETE FROM security_state"))
    with pytest.raises(BackupStateInspectionUnavailable):
        inspect(backup_inspection_db)


def test_invalid_authority_epoch_fails_closed(backup_inspection_db):
    with backup_inspection_db.begin() as conn:
        conn.execute(
            text("ALTER TABLE security_state DROP CONSTRAINT security_state_epoch_non_nil")
        )
        conn.execute(
            text("UPDATE security_state SET authority_epoch_id = :epoch"),
            {"epoch": UUID(int=0)},
        )
    with pytest.raises(BackupStateInspectionUnavailable):
        inspect(backup_inspection_db)


def test_unsupported_postgresql_major_fails_closed(backup_inspection_db):
    with pytest.raises(BackupStateInspectionUnavailable, match="unsupported"):
        inspect(backup_inspection_db, supported_postgresql_major_versions={15})
