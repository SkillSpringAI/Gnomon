"""Migration 030 preserves populated relationship history without inventing commands."""

from uuid import uuid4

from sqlalchemy import text
from test_source_dependence_contract import dependence_context  # noqa: F401

from research_agent.application.migrations import migration_files
from research_agent.application.source_dependence_service import SourceDependenceService
from research_agent.domain.research import SourceRelationshipCreate
from research_agent.persistence.database import SessionFactory, engine


def test_populated_pre_030_history_is_preserved(request):
    task_id, sources = request.getfixturevalue("dependence_context")
    with SessionFactory() as session:
        SourceDependenceService(session).create(
            task_id,
            SourceRelationshipCreate(
                kind="common_origin",
                source_a_id=sources[0],
                source_b_id=sources[1],
                reason="Retain this accepted declaration through upgrade",
            ),
        )

    schema = "dependence_upgrade_" + uuid4().hex
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            origin = connection.scalar(text("SELECT current_schema()"))
            quoted_origin = connection.dialect.identifier_preparer.quote(origin)
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
            migrations = migration_files()
            upgrade = next(p for p in migrations if p.name.startswith("030_"))
            for migration in migrations:
                if migration.name < upgrade.name:
                    connection.exec_driver_sql(migration.read_text(encoding="utf-8"))

            # Populate the real pre-030 schema. JSON conversion maps only columns
            # present in that schema, excluding the not-yet-added command_request.
            for table, key in (
                ("research_tasks", "id"),
                ("research_sources", "task_id"),
                ("source_relationships", "task_id"),
                ("source_relationship_changes", "task_id"),
            ):
                connection.execute(
                    text(
                        f'INSERT INTO "{schema}".{table} '
                        f'SELECT (jsonb_populate_record(NULL::"{schema}".{table}, '
                        f'to_jsonb(original))).* FROM {quoted_origin}.{table} original '
                        f'WHERE original.{key} = :task'
                    ),
                    {"task": task_id},
                )
            before = connection.execute(
                text("SELECT to_jsonb(h) FROM source_relationship_changes h")
            ).scalars().all()
            current = connection.execute(
                text("SELECT to_jsonb(r) FROM source_relationships r")
            ).scalars().all()
            assert len(before) == len(current) == 1
            assert "command_request" not in before[0]

            for _ in range(2):
                connection.exec_driver_sql(upgrade.read_text(encoding="utf-8"))
                after = connection.execute(
                    text("SELECT to_jsonb(h) FROM source_relationship_changes h")
                ).scalars().all()
                assert after == [before[0] | {"command_request": None}]
                assert connection.execute(
                    text("SELECT to_jsonb(r) FROM source_relationships r")
                ).scalars().all() == current
        finally:
            # PostgreSQL transactional DDL removes only this disposable schema.
            transaction.rollback()
