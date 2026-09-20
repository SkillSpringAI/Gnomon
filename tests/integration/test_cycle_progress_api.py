"""Read-only API projection of retained cycle-attempt progress."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from conftest import purge_test_tasks
from fastapi.testclient import TestClient
from sqlalchemy import select

from research_agent.adapters.agents.fake import FakeAgentNetwork
from research_agent.api.app import create_app
from research_agent.persistence.database import SessionFactory, engine
from research_agent.persistence.models import (
    ResearchCycleAttemptRecord,
    ResearchCycleRecord,
)


@pytest.fixture
def progress_api():
    with TestClient(create_app()) as client:
        response = client.post(
            "/investigations",
            json={"title": "Progress projection", "objective": "Report retained truth."},
        )
        task_id = UUID(response.json()["task"]["id"])
        try:
            yield client, task_id
        finally:
            with engine.begin() as connection:
                purge_test_tasks(connection, [task_id])


def latest(client: TestClient, task_id: UUID, cycle_number: int = 1):
    return client.get(
        f"/investigations/{task_id}/cycles/{cycle_number}/attempts/latest"
    )


def test_completed_run_exposes_durable_attempt_progress(progress_api) -> None:
    client, task_id = progress_api
    run = client.post(
        f"/investigations/{task_id}/cycles/1/run",
        json={"max_agents": 1, "objective_indices": [0]},
    )
    assert run.status_code == 200, run.text
    cycle = run.json()["task"]["cycles"][0]

    response = latest(client, task_id)
    assert response.status_code == 200, response.text
    progress = response.json()
    assert progress["cycle_number"] == 1
    assert progress["attempt_status"] == progress["last_durable_stage"] == "COMPLETED"
    assert progress["started_at"] and progress["finished_at"]
    assert progress["recovery_reason"] == "cycle_outcome_recorded"
    assert progress["retained_evidence_ids"] == cycle["evidence_ids"]
    assert progress["retained_claim_ids"] == cycle["claim_ids"]
    assert progress["attempted_objectives"] == cycle["attempted_objectives"]
    assert progress["unresolved_objectives"] == cycle["unresolved_objectives"]
    assert progress["cycle_status"] == "completed"
    assert progress["cycle_active"] is False


def test_unexpected_runner_failure_exposes_committed_progress(
    progress_api, monkeypatch
) -> None:
    client, task_id = progress_api
    original = FakeAgentNetwork.ask
    calls = 0

    def fail_second(network, question):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected runner failure")
        return original(network, question)

    monkeypatch.setattr(FakeAgentNetwork, "ask", fail_second)
    with pytest.raises(RuntimeError, match="injected runner failure"):
        client.post(f"/investigations/{task_id}/cycles/1/run", json={})

    response = latest(client, task_id)
    assert response.status_code == 200, response.text
    progress = response.json()
    assert progress["attempt_status"] == progress["last_durable_stage"] == "FAILED"
    assert progress["finished_at"] is not None
    assert progress["retained_evidence_ids"]
    assert progress["retained_claim_ids"]
    assert progress["attempted_objectives"]
    cycle = client.get(f"/investigations/{task_id}").json()["task"]["cycles"][0]
    assert progress["attempted_objectives"] == cycle["attempted_objectives"]
    assert progress["unresolved_objectives"] == cycle["unresolved_objectives"]
    assert progress["cycle_status"] == "failed"
    assert progress["cycle_active"] is False


def test_latest_attempt_has_deterministic_tie_break_and_preserves_running_state(
    progress_api,
) -> None:
    client, task_id = progress_api
    assert client.post(f"/investigations/{task_id}/cycles/1/start").status_code == 200
    started_at = datetime.now(UTC)
    completed_id = UUID(int=1)
    running_id = UUID(int=2)
    with SessionFactory() as session:
        cycle_id = session.scalar(
            select(ResearchCycleRecord.id).where(
                ResearchCycleRecord.task_id == task_id,
                ResearchCycleRecord.cycle_number == 1,
            )
        )
        assert cycle_id is not None
        session.add_all(
            [
                ResearchCycleAttemptRecord(
                    id=completed_id,
                    task_id=task_id,
                    cycle_id=cycle_id,
                    status="COMPLETED",
                    stage="COMPLETED",
                    started_at=started_at,
                    finished_at=started_at,
                ),
                ResearchCycleAttemptRecord(
                    id=running_id,
                    task_id=task_id,
                    cycle_id=cycle_id,
                    status="RUNNING",
                    stage="QUESTIONING",
                    started_at=started_at,
                ),
            ]
        )
        session.commit()

    progress = latest(client, task_id).json()
    assert progress["attempt_id"] == str(running_id)
    assert progress["attempt_status"] == "RUNNING"
    assert progress["last_durable_stage"] == "QUESTIONING"
    assert progress["finished_at"] is None
    assert progress["cycle_status"] == "active"
    assert progress["cycle_active"] is True


def test_missing_task_cycle_or_attempt_has_one_bounded_response(progress_api) -> None:
    client, task_id = progress_api
    responses = [
        latest(client, task_id),
        latest(client, task_id, 99),
        latest(client, UUID(int=0)),
    ]
    assert [response.status_code for response in responses] == [404, 404, 404]
    assert {response.json()["detail"] for response in responses} == {
        "Cycle attempt not found"
    }
