"""Upgrade the cycle-status value invariant without rewriting historical rows."""

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from research_agent.application.migrations import migration_files, run_migrations
from research_agent.persistence.database import engine


@pytest.fixture
def cycle_status_database():
    database_name = "cycle_status_upgrade_" + uuid4().hex
    admin = create_engine(engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    database = create_engine(engine.url.set(database=database_name))
    created = False
    try:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
            created = True
        yield database
    finally:
        database.dispose()
        if created:
            with admin.connect() as connection:
                connection.exec_driver_sql(f'DROP DATABASE "{database_name}" WITH (FORCE)')
        admin.dispose()


def _pre_m3b_migrations(directory: Path) -> None:
    files = migration_files()
    assert files[-1].name == "036_research_cycles_status_valid.sql"
    for migration in files[:-1]:
        (directory / migration.name).write_bytes(migration.read_bytes())


def _insert_cycle(database, status: str, number: int = 1) -> None:
    with database.begin() as connection:
        task_id = uuid4()
        connection.execute(
            text(
                """
                INSERT INTO research_tasks
                    (id, title, objective, status, brief, plan, created_at, updated_at)
                VALUES (:id, 'Cycle status migration', 'Preserve status.', 'active',
                        '{}'::jsonb, '{}'::jsonb, now(), now())
                """
            ),
            {"id": task_id},
        )
        connection.execute(
            text(
                """
                INSERT INTO research_cycles
                    (id, task_id, cycle_number, objectives, methods, status, created_at)
                VALUES (:id, :task_id, :number, '[]'::jsonb, '[]'::jsonb, :status, now())
                """
            ),
            {"id": uuid4(), "task_id": task_id, "number": number, "status": status},
        )


def test_fresh_database_accepts_all_cycle_statuses_and_rejects_unknown(
    cycle_status_database,
) -> None:
    database = cycle_status_database
    files = migration_files()
    assert run_migrations(database) == [migration.name for migration in files]
    assert run_migrations(database) == []
    for number, status in enumerate(
        ("planned", "active", "completed", "blocked", "failed"), start=1
    ):
        _insert_cycle(database, status, number)
    with pytest.raises(IntegrityError) as raised:
        _insert_cycle(database, "unrecognized", 6)
    assert raised.value.orig.diag.constraint_name == "research_cycles_status_valid"
    with database.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM research_cycles")) == 5
        assert (
            connection.scalar(text("SELECT count(*) FROM research_agent_schema_migrations")) == 36
        )
        assert (
            connection.scalar(
                text(
                    "SELECT attnotnull FROM pg_attribute "
                    "WHERE attrelid = 'research_cycles'::regclass AND attname = 'status'"
                )
            )
            is True
        )


def test_populated_valid_database_upgrades_without_status_rewrite(
    cycle_status_database, tmp_path: Path
) -> None:
    database = cycle_status_database
    _pre_m3b_migrations(tmp_path)
    assert len(run_migrations(database, directory=tmp_path)) == 35
    for number, status in enumerate(
        ("planned", "active", "completed", "blocked", "failed"), start=1
    ):
        _insert_cycle(database, status, number)
    with database.connect() as connection:
        before = connection.execute(
            text("SELECT status, count(*) FROM research_cycles GROUP BY status ORDER BY status")
        ).all()
    assert run_migrations(database) == ["036_research_cycles_status_valid.sql"]
    assert run_migrations(database) == []
    with database.connect() as connection:
        after = connection.execute(
            text("SELECT status, count(*) FROM research_cycles GROUP BY status ORDER BY status")
        ).all()
        assert (
            connection.scalar(text("SELECT count(*) FROM research_agent_schema_migrations")) == 36
        )
    assert after == before


def test_invalid_legacy_status_aborts_upgrade_without_ledger_entry(
    cycle_status_database, tmp_path: Path
) -> None:
    database = cycle_status_database
    _pre_m3b_migrations(tmp_path)
    assert len(run_migrations(database, directory=tmp_path)) == 35
    _insert_cycle(database, "unrecognized")

    with pytest.raises(IntegrityError) as raised:
        run_migrations(database)
    assert raised.value.orig.diag.constraint_name == "research_cycles_status_valid"
    with database.connect() as connection:
        assert (
            connection.scalar(text("SELECT count(*) FROM research_agent_schema_migrations")) == 35
        )
        assert connection.scalar(text("SELECT status FROM research_cycles")) == "unrecognized"
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM pg_constraint "
                    "WHERE conrelid = 'research_cycles'::regclass "
                    "AND conname = 'research_cycles_status_valid'"
                )
            )
            == 0
        )

    # Explicit operator-style repair is test setup, not migration behavior.
    with database.begin() as connection:
        connection.execute(text("UPDATE research_cycles SET status = 'planned'"))
    assert run_migrations(database) == ["036_research_cycles_status_valid.sql"]
