"""Direct SQL cannot bypass critical journal invariants."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from research_agent.application.migrations import run_migrations
from research_agent.persistence.database import engine

run_migrations(engine)


def test_direct_sql_rejects_invalid_memory_version() -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO memory_changes (
                        change_id, task_id, target_type, target_id, operation, actor,
                        timestamp, previous_version, version, proposed_state,
                        resulting_state, reason, provenance, request
                    ) VALUES (
                        :change_id, :task_id, 'claim', :target_id, 'CREATE', 'test',
                        now(), -1, 0, '{}'::jsonb, '{} '::jsonb, 'invalid',
                        '[]'::jsonb, '{}'::jsonb
                    )
                    """
                ),
                {"change_id": uuid4(), "task_id": uuid4(), "target_id": uuid4()},
            )


def test_direct_sql_rejects_unknown_memory_operation() -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO memory_changes (
                        change_id, task_id, target_type, target_id, operation, actor,
                        timestamp, previous_version, version, proposed_state,
                        resulting_state, reason, provenance, request
                    ) VALUES (
                        :change_id, :task_id, 'claim', :target_id, 'INVALID', 'test',
                        now(), 0, 1, '{}'::jsonb, '{}'::jsonb, 'invalid',
                        '[]'::jsonb, '{}'::jsonb
                    )
                    """
                ),
                {"change_id": uuid4(), "task_id": uuid4(), "target_id": uuid4()},
            )


def test_direct_sql_rejects_task_delete_with_retained_audit_event() -> None:
    task_id = uuid4()
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO research_tasks
                        (id, title, objective, status, brief, plan, created_at, updated_at)
                    VALUES (:task_id, 'retention test', 'retention test', 'archived',
                            '{}'::jsonb, '{}'::jsonb, now(), now())
                    """
                ),
                {"task_id": task_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO research_events (id, task_id, event_type, payload, created_at)
                    VALUES (:event_id, :task_id, 'retention.test', '{}'::jsonb, now())
                    """
                ),
                {"event_id": uuid4(), "task_id": task_id},
            )
            connection.execute(
                text("DELETE FROM research_tasks WHERE id = :task_id"),
                {"task_id": task_id},
            )
