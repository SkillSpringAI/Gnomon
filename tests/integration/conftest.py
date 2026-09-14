"""Shared PostgreSQL fixture cleanup that respects retention constraints."""

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import Connection, delete, text

from research_agent.persistence.models import ResearchTaskRecord


def purge_test_tasks(connection: Connection, task_ids: Iterable[UUID]) -> None:
    """Explicitly purge fixture history before removing isolated test tasks."""
    ids = list(task_ids)
    for task_id in ids:
        connection.execute(
            text("DELETE FROM research_events WHERE task_id = :task_id"),
            {"task_id": task_id},
        )
    if ids:
        connection.execute(delete(ResearchTaskRecord).where(ResearchTaskRecord.id.in_(ids)))
