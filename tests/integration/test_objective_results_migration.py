"""Exercise a populated pre-009 schema without changing the application schema."""

import json
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from research_agent.application.migrations import migration_files
from research_agent.persistence.database import engine
from research_agent.persistence.repositories import SqlAlchemyResearchTaskRepository


def test_objective_results_upgrade_preserves_legacy_cycles():
    schema = "objective_upgrade_" + uuid4().hex
    task_id = uuid4()
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            # All schema/data changes are rolled back, including on assertion failure.
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}", public')
            files = migration_files()
            upgrade = next(path for path in files if path.name == "009_objective_results.sql")
            for path in files:
                if path.name < upgrade.name:
                    connection.exec_driver_sql(path.read_text(encoding="utf-8"))
            connection.execute(
                text("""
                INSERT INTO research_tasks
                    (id, title, objective, status, brief, plan, created_at, updated_at)
                VALUES (:id, 'Legacy investigation', 'Preserve evidence.', 'active',
                    '{}'::jsonb, CAST(:plan AS jsonb), now(), now())
            """),
                {
                    "id": task_id,
                    "plan": json.dumps(
                        {
                            "summary": "Legacy plan",
                            "first_cycle_objectives": ["Review evidence."],
                            "proposed_methods": [],
                            "open_questions": [],
                        }
                    ),
                },
            )
            for number, status in enumerate(["planned", "completed", "blocked"], start=1):
                connection.execute(
                    text("""
                    INSERT INTO research_cycles
                        (task_id, cycle_number, objectives, methods, status, created_at,
                         result_summary, attempted_objectives, evidence_ids, claim_ids)
                    VALUES (:task, :number, '["Review evidence."]'::jsonb, '[]'::jsonb,
                        :status, now(), 'Legacy history', '["Review evidence."]'::jsonb,
                        CAST(:sources AS jsonb), CAST(:claims AS jsonb))
                """),
                    {
                        "task": task_id,
                        "number": number,
                        "status": status,
                        "sources": json.dumps([str(uuid4())]),
                        "claims": json.dumps([str(uuid4())]),
                    },
                )
            before = (
                connection.execute(
                    text("SELECT to_jsonb(c) FROM research_cycles c ORDER BY cycle_number")
                )
                .scalars()
                .all()
            )
            sql = upgrade.read_text(encoding="utf-8")
            connection.exec_driver_sql(sql)
            connection.exec_driver_sql(sql)
            after = (
                connection.execute(
                    text("SELECT to_jsonb(c) FROM research_cycles c ORDER BY cycle_number")
                )
                .scalars()
                .all()
            )
            assert all(row.pop("objective_results") == [] for row in after)
            assert after == before
            with Session(bind=connection) as session:
                task = SqlAlchemyResearchTaskRepository(session).get(task_id)
                assert len(task.cycles) == 3
                assert all(cycle.objective_results == [] for cycle in task.cycles)
                assert [cycle.status.value for cycle in task.cycles] == [
                    "planned",
                    "completed",
                    "blocked",
                ]
        finally:
            transaction.rollback()
