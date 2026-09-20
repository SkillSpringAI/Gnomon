"""Read-only API projection of retained cycle-attempt progress."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from conftest import purge_test_tasks
from fastapi.testclient import TestClient
from sqlalchemy import select

from research_agent.adapters.agents.fake import FakeAgentNetwork
from research_agent.api.app import create_app
from research_agent.application import agent_cycle_runner
from research_agent.application.research_service import ResearchService
from research_agent.application.security_capability import SecurityCapabilityDenied
from research_agent.persistence.database import SessionFactory, engine
from research_agent.persistence.models import (
    ResearchCycleAttemptRecord,
    ResearchCycleRecord,
    ResearchEventRecord,
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


def test_observing_retained_progress_does_not_mutate_state_or_audit(progress_api) -> None:
    client, task_id = progress_api
    run = client.post(
        f"/investigations/{task_id}/cycles/1/run",
        json={"max_agents": 1, "objective_indices": [0]},
    )
    assert run.status_code == 200, run.text

    with SessionFactory() as session:
        before = {
            "attempt": session.scalar(
                select(ResearchCycleAttemptRecord).where(
                    ResearchCycleAttemptRecord.task_id == task_id
                )
            ),
            "cycle": session.scalar(
                select(ResearchCycleRecord).where(
                    ResearchCycleRecord.task_id == task_id,
                    ResearchCycleRecord.cycle_number == 1,
                )
            ),
            "audit_count": session.query(ResearchEventRecord)
            .filter(ResearchEventRecord.task_id == task_id)
            .count(),
        }
        assert before["attempt"] is not None and before["cycle"] is not None
        before_values = (
            before["attempt"].status,
            before["attempt"].stage,
            before["attempt"].finished_at,
            before["attempt"].recovery_reason,
            before["cycle"].status,
            before["cycle"].completed_at,
            before["cycle"].recovery_reason,
            before["audit_count"],
        )

    first = latest(client, task_id)
    second = latest(client, task_id)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()

    with SessionFactory() as session:
        attempt = session.scalar(
            select(ResearchCycleAttemptRecord).where(
                ResearchCycleAttemptRecord.task_id == task_id
            )
        )
        cycle = session.scalar(
            select(ResearchCycleRecord).where(
                ResearchCycleRecord.task_id == task_id,
                ResearchCycleRecord.cycle_number == 1,
            )
        )
        audit_count = session.query(ResearchEventRecord).filter(
            ResearchEventRecord.task_id == task_id
        ).count()
        assert attempt is not None and cycle is not None
        assert (
            attempt.status,
            attempt.stage,
            attempt.finished_at,
            attempt.recovery_reason,
            cycle.status,
            cycle.completed_at,
            cycle.recovery_reason,
            audit_count,
        ) == before_values


def test_failed_closure_keeps_attempt_and_cycle_unresolved(progress_api, monkeypatch) -> None:
    client, task_id = progress_api

    def reject_outcome(service, task_id, cycle_number, outcome, **kwargs):
        raise SecurityCapabilityDenied("outcome authority unavailable")

    def reject_interruption(service, task_id, cycle_number, attempt_id, *, caller):
        raise SecurityCapabilityDenied("containment authority unavailable")

    monkeypatch.setattr(ResearchService, "record_cycle_outcome", reject_outcome)
    monkeypatch.setattr(agent_cycle_runner.CycleInterruptionService, "close", reject_interruption)

    response = client.post(
        f"/investigations/{task_id}/cycles/1/run",
        json={"scenario": "unresponsive", "max_agents": 1},
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Security policy denied capability"}

    progress = latest(client, task_id)
    assert progress.status_code == 200, progress.text
    payload = progress.json()
    assert payload["attempt_status"] == "RUNNING"
    assert payload["last_durable_stage"] == "QUESTIONING"
    assert payload["finished_at"] is None
    assert payload["cycle_status"] == "active"
    assert payload["cycle_active"] is True


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
