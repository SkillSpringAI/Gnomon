"""Stopping decisions validate and persist cycle-qualified objective references."""

from uuid import uuid4

from sqlalchemy import text
from test_stopping_decisions import _cleanup, _new_task, _request

from research_agent.api.app import create_app
from research_agent.persistence.database import engine


def test_objective_reference_without_cycles_returns_conflict_not_index_error():
    with _client() as client:
        task, readiness = _new_task(client)
        try:
            with engine.begin() as connection:
                connection.execute(
                    text("DELETE FROM research_cycles WHERE task_id = :task_id"),
                    {"task_id": task},
                )
            readiness = client.get(
                f"/investigations/{task}/stopping-decision/readiness"
            ).json()
            response = client.post(
                f"/investigations/{task}/stopping-decision",
                json=_request(
                    readiness,
                    objective_cycle_number=1,
                    objective_indices=[0],
                ),
            )
            assert response.status_code == 409
            assert "existing cycle" in response.json()["detail"]
        finally:
            _cleanup(task)


def test_objective_reference_requires_existing_cycle_and_persists_identity():
    with _client() as client:
        task, readiness = _new_task(client)
        try:
            invalid = client.post(
                f"/investigations/{task}/stopping-decision",
                json=_request(
                    readiness,
                    objective_cycle_number=99,
                    objective_indices=[0],
                ),
            )
            assert invalid.status_code == 409
            assert "unknown cycle" in invalid.json()["detail"]

            invalid_index = client.post(
                f"/investigations/{task}/stopping-decision",
                json=_request(
                    readiness,
                    objective_cycle_number=1,
                    objective_indices=[999],
                ),
            )
            assert invalid_index.status_code == 409
            assert "unknown objective" in invalid_index.json()["detail"]

            operation_id = uuid4()
            accepted = client.post(
                f"/investigations/{task}/stopping-decision",
                json=_request(readiness, operation_id=operation_id, objective_indices=[0]),
            )
            assert accepted.status_code == 201, accepted.text
            decision = accepted.json()
            assert decision["objective_cycle_number"] == 1
            assert decision["objective_indices"] == [0]
            assert client.post(
                f"/investigations/{task}/stopping-decision",
                json=_request(readiness, operation_id=operation_id, objective_indices=[0]),
            ).json() == decision
            history = client.get(f"/investigations/{task}/stopping-decision/history").json()
            assert history[0]["resulting_state"]["objective_cycle_number"] == 1
        finally:
            _cleanup(task)


def _client():
    from fastapi.testclient import TestClient

    return TestClient(create_app())
