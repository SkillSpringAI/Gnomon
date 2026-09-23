"""Stopping replay compares the accepted command, not derived decision fields."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_stopping_decisions import _cleanup, _new_task, _request

from research_agent.api.app import create_app
from research_agent.application import stopping_decision_service
from research_agent.application.security_capability import SecurityCapabilityDenied
from research_agent.application.stopping_decision_service import (
    StoppingDecisionActor,
    StoppingDecisionConflict,
    StoppingDecisionService,
)
from research_agent.domain.research import StoppingDecisionCreate
from research_agent.persistence.database import SessionFactory
from research_agent.persistence.models import StoppingDecisionChangeRecord, StoppingDecisionRecord


def test_retry_preserves_server_added_limitations():
    with TestClient(create_app()) as client:
        task, _ = _new_task(client)
        try:
            assert (
                client.post(
                    f"/investigations/{task}/sources",
                    json={"source_type": "document", "title": "Evidence", "content": "Observed."},
                ).status_code
                == 201
            )
            ready = client.get(f"/investigations/{task}/stopping-decision/readiness").json()
            body = _request(ready)
            first = client.post(f"/investigations/{task}/stopping-decision", json=body)
            assert first.status_code == 201, first.text
            assert first.json()["limitations"] and body["limitations"] == []
            retry = client.post(f"/investigations/{task}/stopping-decision", json=body)
            assert retry.status_code == 201, retry.text
            assert retry.json() == first.json()
            assert len(client.get(f"/investigations/{task}/stopping-decision/history").json()) == 1
            events = client.get(f"/investigations/{task}/events").json()
            assert sum(e["event_type"] == "task.stopping_decision_recorded" for e in events) == 1
        finally:
            _cleanup(task)


@pytest.mark.parametrize("field,value", [("expected_revision", 999), ("expected_status", "paused")])
def test_retry_rejects_changed_command_preconditions(field, value):
    with TestClient(create_app()) as client:
        task, ready = _new_task(client)
        try:
            body = _request(ready)
            assert (
                client.post(f"/investigations/{task}/stopping-decision", json=body).status_code
                == 201
            )
            response = client.post(
                f"/investigations/{task}/stopping-decision", json=body | {field: value}
            )
            assert response.status_code == 409
        finally:
            _cleanup(task)


def test_retry_rejects_different_trusted_actor():
    with TestClient(create_app()) as client:
        task, ready = _new_task(client)
        try:
            body = _request(ready)
            assert (
                client.post(f"/investigations/{task}/stopping-decision", json=body).status_code
                == 201
            )
            with SessionFactory() as session:
                service = StoppingDecisionService(session, StoppingDecisionActor(actor_id="other"))
                with pytest.raises(StoppingDecisionConflict):
                    service.decide(task, StoppingDecisionCreate.model_validate(body))
        finally:
            _cleanup(task)


@pytest.mark.parametrize(
    "metadata", [None, {"version": 2}, {"unexpected": "field"}, "early_development_v1"]
)
def test_unprovable_command_replay_is_refused_without_changing_history(metadata):
    with TestClient(create_app()) as client:
        task, ready = _new_task(client)
        try:
            body = _request(ready)
            accepted = client.post(f"/investigations/{task}/stopping-decision", json=body)
            assert accepted.status_code == 201
            with SessionFactory() as session:
                change = session.scalar(
                    select(StoppingDecisionChangeRecord).where(
                        StoppingDecisionChangeRecord.task_id == task
                    )
                )
                original_state = change.resulting_state
                if metadata == "early_development_v1":
                    metadata = StoppingDecisionService._canonical_request(
                        StoppingDecisionCreate.model_validate(body)
                    )
                    metadata["request"].pop("objective_cycle_number")
                change.command_request = metadata
                session.commit()
            assert client.get(f"/investigations/{task}/stopping-decision").json() == accepted.json()
            assert (
                client.post(f"/investigations/{task}/stopping-decision", json=body).status_code
                == 409
            )
            with SessionFactory() as session:
                change = session.scalar(
                    select(StoppingDecisionChangeRecord).where(
                        StoppingDecisionChangeRecord.task_id == task
                    )
                )
                assert change.resulting_state == original_state
                assert change.command_request == metadata
        finally:
            _cleanup(task)


def test_retry_returns_history_and_still_requires_current_authority(monkeypatch):
    with TestClient(create_app()) as client:
        task, ready = _new_task(client)
        try:
            body = _request(ready, limitations=["Operator caveat", "Operator caveat"])
            accepted = client.post(f"/investigations/{task}/stopping-decision", json=body)
            assert accepted.status_code == 201
            with SessionFactory() as session:
                current = session.scalar(
                    select(StoppingDecisionRecord).where(StoppingDecisionRecord.task_id == task)
                )
                # Deliberately alter only the disposable projection, not history.
                current.rationale = "Later projection value must not define retry output"
                session.commit()
            normalized = body | {"limitations": ["Operator caveat"]}
            retry = client.post(f"/investigations/{task}/stopping-decision", json=normalized)
            assert retry.status_code == 201
            assert retry.json() == accepted.json()

            def deny(*args, **kwargs):
                raise SecurityCapabilityDenied("denied")

            monkeypatch.setattr(stopping_decision_service, "require_locked_capability", deny)
            assert (
                client.post(f"/investigations/{task}/stopping-decision", json=body).status_code
                == 403
            )
        finally:
            _cleanup(task)
