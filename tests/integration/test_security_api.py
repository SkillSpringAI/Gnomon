import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, text

from research_agent.api.app import create_app
from research_agent.api.routes import security as security_routes
from research_agent.application.security_capability import (
    SecurityCapability,
    SecurityCapabilityDenied,
)
from research_agent.persistence.database import engine
from research_agent.persistence.models import SecurityTransitionRecord


def reset_security_state() -> None:
    with engine.begin() as connection:
        connection.execute(delete(SecurityTransitionRecord))
        connection.execute(
            text(
                "UPDATE security_state SET state = 'normal', version = 1, "
                "updated_at = now() WHERE id = 1"
            )
        )


@pytest.fixture(autouse=True)
def clean_security_state():
    reset_security_state()
    yield
    reset_security_state()


def test_security_transition_history_enforces_read_audit(monkeypatch) -> None:
    def deny(session, capability):
        assert capability is SecurityCapability.READ_AUDIT
        raise SecurityCapabilityDenied("denied by test policy")

    monkeypatch.setattr(security_routes, "require_capability", deny)
    with TestClient(create_app()) as client:
        response = client.get("/security/transitions")
    assert response.status_code == 403
    assert response.json() == {"detail": "Security policy denied capability"}


def test_security_state_and_transition_history_are_operator_visible() -> None:
    with TestClient(create_app()) as client:
        initial = client.get("/security/state")
        assert initial.status_code == 200
        assert initial.json() == {"state": "normal", "version": 1}

        changed = client.post(
            "/security/transitions",
            json={
                "expected_version": 1,
                "requested_state": "lockdown",
                "reason_code": "OPERATOR_LOCKDOWN",
            },
        )
        assert changed.status_code == 200
        assert changed.json()["new_state"] == "lockdown"
        assert changed.json()["security_state_version"] == 2

        history = client.get("/security/transitions")
        assert history.status_code == 200
        assert len(history.json()) == 1
        assert history.json()[0]["reason_code"] == "OPERATOR_LOCKDOWN"

        stale = client.post(
            "/security/transitions",
            json={
                "expected_version": 1,
                "requested_state": "degraded",
                "reason_code": "OPERATOR_DEGRADED_MODE",
            },
        )
        assert stale.status_code == 409


def test_same_state_api_request_is_idempotent_without_new_history() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/security/transitions",
            json={
                "expected_version": 1,
                "requested_state": "normal",
                "reason_code": "OPERATOR_DEGRADED_MODE",
            },
        )
        assert response.status_code == 200
        assert response.json()["transition_id"] is None
        assert client.get("/security/transitions").json() == []


def test_lockdown_blocks_lifecycle_start_and_provider_admission() -> None:
    with TestClient(create_app()) as client:
        created = client.post(
            "/investigations",
            json={
                "title": "Security boundary test",
                "objective": "Verify restrictive capability enforcement.",
                "questions": [{"question": "Can work begin?"}],
            },
        )
        assert created.status_code == 201
        task_id = created.json()["task"]["id"]
        lockdown = client.post(
            "/security/transitions",
            json={
                "expected_version": 1,
                "requested_state": "lockdown",
                "reason_code": "OPERATOR_LOCKDOWN",
            },
        )
        assert lockdown.status_code == 200
        assert client.post(f"/investigations/{task_id}/cycles").status_code == 403
        assert client.post(f"/investigations/{task_id}/cycles/1/start").status_code == 403
        assert client.post(f"/investigations/{task_id}/report/draft").status_code == 403

        source_fetch = client.post(
            f"/investigations/{task_id}/sources/fetch",
            json={
                "uri": "https://example.test/evidence",
                "source_type": "web_page",
                "reliability_score": 0.5,
            },
        )
        assert source_fetch.status_code == 403
