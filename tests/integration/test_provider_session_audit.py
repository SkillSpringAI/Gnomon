"""Durable, redacted provider-session lifecycle audit contracts."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, text

from research_agent.api.app import create_app
from research_agent.application import provider_session_audit as audit_module
from research_agent.application.security_capability import (
    SecurityCapability,
    SecurityCapabilityDenied,
)
from research_agent.persistence.database import engine
from research_agent.persistence.models import ProviderSessionEventRecord


@pytest.fixture(autouse=True)
def clean_provider_session_events():
    with engine.begin() as connection:
        connection.execute(delete(ProviderSessionEventRecord))
        connection.execute(
            text(
                "UPDATE security_state SET state = 'normal', version = 1, "
                "updated_at = now() WHERE id = 1"
            )
        )
    yield
    with engine.begin() as connection:
        connection.execute(delete(ProviderSessionEventRecord))
        connection.execute(
            text(
                "UPDATE security_state SET state = 'normal', version = 1, "
                "updated_at = now() WHERE id = 1"
            )
        )


def test_provider_session_create_delete_and_repeat_are_audited_without_secrets(
    monkeypatch,
):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    from research_agent.config.settings import get_settings

    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            created = client.post(
                "/provider/session",
                json={"bearer_token": "secret-" + uuid4().hex, "ttl_seconds": 600},
            )
            assert created.status_code == 201
            assert "secret-" not in created.text
            deleted = client.delete("/provider/session")
            assert deleted.status_code == 204
            repeated = client.delete("/provider/session")
            assert repeated.status_code == 204

            response = client.get("/provider/audit")
            assert response.status_code == 200
            payload = response.json()
            assert {event["reason"] for event in payload} == {
                "deleted",
                "already_absent",
                "created",
            }
            assert all(event["credential_mode"] == "session_bearer_token" for event in payload)
            assert "secret-" not in response.text
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        get_settings.cache_clear()


def test_replacing_active_provider_session_audits_revoke_then_create(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    from research_agent.config.settings import get_settings

    get_settings.cache_clear()
    first_secret = "first-secret-" + uuid4().hex
    second_secret = "second-secret-" + uuid4().hex
    try:
        with TestClient(create_app()) as client:
            first = client.post(
                "/provider/session",
                json={"bearer_token": first_secret, "ttl_seconds": 600},
            )
            assert first.status_code == 201
            replaced = client.post(
                "/provider/session",
                json={"bearer_token": second_secret, "ttl_seconds": 900},
            )
            assert replaced.status_code == 201

            events = client.get("/provider/audit").json()
            assert [event["operation"] for event in events].count("CREATE") == 2
            assert [event["operation"] for event in events].count("DELETE") == 1
            assert all(event["reason"] in {"created", "deleted"} for event in events)
            assert first_secret not in replaced.text
            assert second_secret not in replaced.text
            assert first_secret not in str(events)
            assert second_secret not in str(events)
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        get_settings.cache_clear()


def test_provider_session_audit_read_enforces_read_audit(monkeypatch):
    def deny(session, capability):
        assert capability is SecurityCapability.READ_AUDIT
        raise SecurityCapabilityDenied("denied")

    monkeypatch.setattr(audit_module, "require_capability", deny)
    with TestClient(create_app()) as client:
        response = client.get("/provider/audit")
    assert response.status_code == 403
