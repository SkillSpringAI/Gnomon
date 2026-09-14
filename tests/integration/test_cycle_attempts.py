"""Durable cycle execution-attempt contracts."""

from uuid import UUID

from conftest import purge_test_tasks
from fastapi.testclient import TestClient

from research_agent.api.app import create_app
from research_agent.persistence.database import SessionFactory, engine
from research_agent.persistence.models import ResearchCycleAttemptRecord


def test_completed_cycle_has_durable_attempt_identity() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/investigations",
            json={"title": "Attempt trace", "objective": "Verify durable execution."},
        )
        task_id = UUID(response.json()["task"]["id"])
        try:
            assert client.post(f"/investigations/{task_id}/cycles").status_code == 200
            result = client.post(f"/investigations/{task_id}/cycles/1/run", json={})
            assert result.status_code == 200, result.text
            with SessionFactory() as session:
                attempts = (
                    session.query(ResearchCycleAttemptRecord).filter_by(task_id=task_id).all()
                )
                assert len(attempts) == 1
                assert attempts[0].status == "COMPLETED"
                assert attempts[0].stage == "COMPLETED"
                assert attempts[0].finished_at is not None
        finally:
            with engine.begin() as connection:
                purge_test_tasks(connection, [task_id])
