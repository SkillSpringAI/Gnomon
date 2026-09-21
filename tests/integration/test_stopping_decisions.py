"""Operator-controlled stopping-decision contracts."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from conftest import purge_test_tasks
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from research_agent.api.app import create_app
from research_agent.application import stopping_decision_service
from research_agent.application.security_capability import SecurityCapabilityDenied
from research_agent.persistence.database import SessionFactory, engine
from research_agent.persistence.models import (
    ResearchCycleAttemptRecord,
    ResearchCycleRecord,
    ResearchEventRecord,
    StoppingDecisionChangeRecord,
    StoppingDecisionRecord,
)


def _cleanup(task_id: UUID) -> None:
    with engine.begin() as connection:
        connection.execute(
            delete(StoppingDecisionChangeRecord).where(
                StoppingDecisionChangeRecord.task_id == task_id
            )
        )
        connection.execute(
            delete(StoppingDecisionRecord).where(StoppingDecisionRecord.task_id == task_id)
        )
        connection.execute(
            delete(ResearchCycleAttemptRecord).where(ResearchCycleAttemptRecord.task_id == task_id)
        )
        purge_test_tasks(connection, [task_id])


def _new_task(client: TestClient) -> tuple[UUID, dict]:
    response = client.post(
        "/investigations",
        json={"title": "Stopping decision", "objective": "Test operator conclusion."},
    )
    assert response.status_code == 201, response.text
    task_id = UUID(response.json()["task"]["id"])
    readiness = client.get(f"/investigations/{task_id}/stopping-decision/readiness")
    assert readiness.status_code == 200, readiness.text
    return task_id, readiness.json()


def _request(readiness: dict, *, operation_id: UUID | None = None, **overrides: object) -> dict:
    body: dict[str, object] = {
        "reason": "evidence_sufficient",
        "rationale": "The operator reviewed the available bounded evidence.",
        "expected_status": readiness["task_status"],
        "expected_revision": readiness["task_revision"],
        "expected_evidence_fingerprint": readiness["evidence_fingerprint"],
        "source_ids": [],
        "claim_ids": [],
        "objective_indices": [],
        "review_ids": [],
        "limitations": [],
        "runtime_limit_evidence": [],
        "operation_id": str(operation_id or uuid4()),
    }
    body.update(overrides)
    return body


def test_stopping_decision_is_atomic_idempotent_and_audited() -> None:
    with TestClient(create_app()) as client:
        task_id, readiness = _new_task(client)
        operation_id = uuid4()
        request = _request(readiness, operation_id=operation_id)
        try:
            first = client.post(f"/investigations/{task_id}/stopping-decision", json=request)
            assert first.status_code == 201, first.text
            decision = first.json()
            assert decision["reason"] == "evidence_sufficient"
            assert client.get(f"/investigations/{task_id}").json()["task"]["status"] == "concluded"

            retry = client.post(f"/investigations/{task_id}/stopping-decision", json=request)
            assert retry.status_code == 201, retry.text
            assert retry.json() == decision

            history = client.get(f"/investigations/{task_id}/stopping-decision/history")
            assert history.status_code == 200
            assert len(history.json()) == 1
            assert history.json()[0]["resulting_state"] == decision
            events = client.get(f"/investigations/{task_id}/events").json()
            stopping_events = [
                event
                for event in events
                if event["event_type"] == "task.stopping_decision_recorded"
            ]
            assert len(stopping_events) == 1
            assert "rationale" not in stopping_events[0]["payload"]
            assert "source_ids" not in stopping_events[0]["payload"]
        finally:
            _cleanup(task_id)


def test_stale_basis_and_conflicting_retry_are_rejected() -> None:
    with TestClient(create_app()) as client:
        task_id, readiness = _new_task(client)
        operation_id = uuid4()
        try:
            unknown_review = _request(
                readiness,
                operation_id=uuid4(),
                review_ids=[str(uuid4())],
            )
            assert client.post(
                f"/investigations/{task_id}/stopping-decision", json=unknown_review
            ).status_code == 409

            stale = _request(
                readiness,
                operation_id=uuid4(),
                expected_evidence_fingerprint="0" * 64,
            )
            response = client.post(f"/investigations/{task_id}/stopping-decision", json=stale)
            assert response.status_code == 409
            assert client.get(f"/investigations/{task_id}").json()["task"]["status"] == "active"

            request = _request(readiness, operation_id=operation_id)
            assert client.post(
                f"/investigations/{task_id}/stopping-decision", json=request
            ).status_code == 201
            conflict = _request(
                readiness,
                operation_id=operation_id,
                rationale="A different payload must not reuse the operation.",
            )
            assert (
                client.post(
                    f"/investigations/{task_id}/stopping-decision", json=conflict
                ).status_code
                == 409
            )
        finally:
            _cleanup(task_id)


def test_active_cycle_attempt_blocks_conclusion() -> None:
    with TestClient(create_app()) as client:
        task_id, readiness = _new_task(client)
        cycle_response = client.post(f"/investigations/{task_id}/cycles")
        assert cycle_response.status_code == 200, cycle_response.text
        try:
            readiness = client.get(
                f"/investigations/{task_id}/stopping-decision/readiness"
            ).json()
            with SessionFactory() as session:
                cycle = session.scalar(
                    select(ResearchCycleRecord).where(
                        ResearchCycleRecord.task_id == task_id,
                        ResearchCycleRecord.cycle_number == 1,
                    )
                )
                assert cycle is not None
                session.add(
                    ResearchCycleAttemptRecord(
                        id=uuid4(),
                        task_id=task_id,
                        cycle_id=cycle.id,
                        status="RUNNING",
                        stage="STARTED",
                            started_at=datetime.now(UTC),
                        evidence_ids=[],
                        claim_ids=[],
                    )
                )
                session.commit()
            response = client.post(
                f"/investigations/{task_id}/stopping-decision", json=_request(readiness)
            )
            assert response.status_code == 409
            assert "active cycle attempt" in response.json()["detail"]
        finally:
            _cleanup(task_id)


def test_concurrent_decisions_allow_one_winner() -> None:
    with TestClient(create_app()) as setup_client:
        task_id, readiness = _new_task(setup_client)
        try:
            barrier = Barrier(2)

            def submit(client: TestClient) -> int:
                barrier.wait()
                response = client.post(
                    f"/investigations/{task_id}/stopping-decision",
                    json=_request(readiness, operation_id=uuid4()),
                )
                return response.status_code

            with TestClient(create_app()) as first, TestClient(create_app()) as second:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    statuses = list(executor.map(submit, (first, second)))
            assert sorted(statuses) == [201, 409]
            history = setup_client.get(
                f"/investigations/{task_id}/stopping-decision/history"
            )
            assert history.status_code == 200
            assert len(history.json()) == 1
        finally:
            _cleanup(task_id)


def test_audit_failure_rolls_back_decision_and_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    with TestClient(create_app()) as client:
        task_id, readiness = _new_task(client)
        try:
            def fail(*args: object, **kwargs: object) -> None:
                raise RuntimeError("audit unavailable")

            monkeypatch.setattr(stopping_decision_service.AuditService, "stage", fail)
            with pytest.raises(RuntimeError, match="audit unavailable"):
                with SessionFactory() as session:
                    stopping_decision_service.StoppingDecisionService(session).decide(
                        task_id,
                        stopping_decision_service.StoppingDecisionCreate(**_request(readiness)),
                    )
            assert client.get(f"/investigations/{task_id}").json()["task"]["status"] == "active"
            with SessionFactory() as session:
                assert session.scalar(
                    select(StoppingDecisionRecord).where(StoppingDecisionRecord.task_id == task_id)
                ) is None
                assert session.scalar(
                    select(ResearchEventRecord).where(ResearchEventRecord.task_id == task_id)
                ) is not None
        finally:
            _cleanup(task_id)


def test_capability_denial_does_not_write(monkeypatch: pytest.MonkeyPatch) -> None:
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        task_id, readiness = _new_task(client)
        try:
            def deny(*args: object, **kwargs: object) -> object:
                raise SecurityCapabilityDenied("denied")

            monkeypatch.setattr(stopping_decision_service, "require_locked_capability", deny)
            response = client.post(
                f"/investigations/{task_id}/stopping-decision", json=_request(readiness)
            )
            assert response.status_code == 403
            assert client.get(f"/investigations/{task_id}").json()["task"]["status"] == "active"
        finally:
            _cleanup(task_id)


def test_report_exposes_decision_and_legacy_conclusion_as_unspecified() -> None:
    with TestClient(create_app()) as client:
        task_id, readiness = _new_task(client)
        try:
            accepted = client.post(
                f"/investigations/{task_id}/stopping-decision",
                json=_request(readiness),
            )
            assert accepted.status_code == 201, accepted.text
            report = client.get(f"/investigations/{task_id}/report")
            assert report.status_code == 200, report.text
            assert report.json()["stopping_decision"]["reason"] == "evidence_sufficient"
            assert report.json()["stopping_decision"]["stale"] is False
        finally:
            _cleanup(task_id)

    with TestClient(create_app()) as client:
        task_id, _ = _new_task(client)
        try:
            concluded = client.patch(
                f"/investigations/{task_id}/status",
                json={"expected_status": "active", "status": "concluded"},
            )
            assert concluded.status_code == 200, concluded.text
            report = client.get(f"/investigations/{task_id}/report")
            assert report.status_code == 200, report.text
            assert report.json()["stopping_decision"]["reason"] == "unspecified"
            assert report.json()["stopping_decision"]["limitations"]
        finally:
            _cleanup(task_id)
