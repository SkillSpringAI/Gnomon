"""Durable, redacted provider-session lifecycle audit contracts."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, text

from research_agent.api.app import create_app
from research_agent.api.routes import provider as provider_module
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


def test_failed_replacement_commit_restores_old_session_and_cookie(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    from research_agent.config.settings import get_settings

    get_settings.cache_clear()
    first_secret = "first-secret-" + uuid4().hex
    second_secret = "second-secret-" + uuid4().hex
    try:
        with TestClient(create_app(), raise_server_exceptions=False) as client:
            created = client.post(
                "/provider/session",
                json={"bearer_token": first_secret, "ttl_seconds": 600},
            )
            assert created.status_code == 201
            old_session_id = client.cookies.get("provider_session")
            assert old_session_id is not None

            real_factory = provider_module.SessionFactory

            @contextmanager
            def failing_factory():
                with real_factory() as session:
                    def fail_commit():
                        raise RuntimeError("injected audit commit failure")

                    session.commit = fail_commit
                    yield session

            monkeypatch.setattr(provider_module, "SessionFactory", failing_factory)
            failed = client.post(
                "/provider/session",
                json={"bearer_token": second_secret, "ttl_seconds": 900},
            )
            assert failed.status_code == 500
            assert client.cookies.get("provider_session") == old_session_id
            assert provider_module.provider_sessions.get(old_session_id) == first_secret
            assert second_secret not in failed.text
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        get_settings.cache_clear()


def test_failed_replacement_stage_restores_old_session_and_cookie(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    from research_agent.config.settings import get_settings

    get_settings.cache_clear()
    first_secret = "first-stage-secret-" + uuid4().hex
    second_secret = "second-stage-secret-" + uuid4().hex
    try:
        with TestClient(create_app(), raise_server_exceptions=False) as client:
            created = client.post(
                "/provider/session",
                json={"bearer_token": first_secret, "ttl_seconds": 600},
            )
            assert created.status_code == 201
            old_session_id = client.cookies.get("provider_session")
            assert old_session_id is not None

            def fail_stage(*args, **kwargs):
                raise RuntimeError("injected audit stage failure")

            monkeypatch.setattr(audit_module.ProviderSessionAuditService, "stage", fail_stage)
            failed = client.post(
                "/provider/session",
                json={"bearer_token": second_secret, "ttl_seconds": 900},
            )
            assert failed.status_code == 500
            assert client.cookies.get("provider_session") == old_session_id
            assert provider_module.provider_sessions.get(old_session_id) == first_secret
            assert second_secret not in failed.text
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        get_settings.cache_clear()


def test_concurrent_replacement_and_delete_have_bounded_outcomes(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    from research_agent.config.settings import get_settings

    get_settings.cache_clear()
    old_secret = "concurrent-old-" + uuid4().hex
    replacement_secret = "concurrent-replacement-" + uuid4().hex
    try:
        with TestClient(create_app()) as setup:
            created = setup.post(
                "/provider/session",
                json={"bearer_token": old_secret, "ttl_seconds": 600},
            )
            assert created.status_code == 201
            old_session_id = setup.cookies.get("provider_session")
            assert old_session_id is not None

            barrier = Barrier(2)

            def replace() -> int:
                with TestClient(create_app()) as client:
                    client.cookies.set("provider_session", old_session_id)
                    barrier.wait()
                    return client.post(
                        "/provider/session",
                        json={"bearer_token": replacement_secret, "ttl_seconds": 900},
                    ).status_code

            def remove() -> int:
                with TestClient(create_app()) as client:
                    client.cookies.set("provider_session", old_session_id)
                    barrier.wait()
                    return client.delete("/provider/session").status_code

            with ThreadPoolExecutor(max_workers=2) as executor:
                statuses = list(executor.map(lambda task: task(), (replace, remove)))
            assert sorted(statuses) == [201, 204]
            assert provider_module.provider_sessions.get(old_session_id) is None
            audit = setup.get("/provider/audit")
            assert audit.status_code == 200
            assert all(old_secret not in str(event) for event in audit.json())
            assert all(replacement_secret not in str(event) for event in audit.json())
    finally:
        provider_module.provider_sessions.delete(
            old_session_id if "old_session_id" in locals() else None
        )
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        get_settings.cache_clear()


def test_concurrent_replacements_have_one_revoke_and_two_active_results(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    from research_agent.config.settings import get_settings

    get_settings.cache_clear()
    old_secret = "double-old-" + uuid4().hex
    replacement_secrets = ["double-one-" + uuid4().hex, "double-two-" + uuid4().hex]
    try:
        with TestClient(create_app()) as setup:
            created = setup.post(
                "/provider/session",
                json={"bearer_token": old_secret, "ttl_seconds": 600},
            )
            assert created.status_code == 201
            old_session_id = setup.cookies.get("provider_session")
            assert old_session_id is not None
            barrier = Barrier(2)

            def replace(secret: str) -> tuple[int, str | None]:
                with TestClient(create_app()) as client:
                    client.cookies.set("provider_session", old_session_id)
                    barrier.wait()
                    response = client.post(
                        "/provider/session",
                        json={"bearer_token": secret, "ttl_seconds": 900},
                    )
                    return response.status_code, client.cookies.get(
                        "provider_session", domain="testserver.local"
                    )

            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(replace, replacement_secrets))
            assert [result[0] for result in results] == [201, 201]
            assert provider_module.provider_sessions.get(old_session_id) is None
            assert all(
                session_id
                and provider_module.provider_sessions.get(session_id) in replacement_secrets
                for _, session_id in results
            )
            audit = setup.get("/provider/audit")
            assert audit.status_code == 200
            events = audit.json()
            assert [event["operation"] for event in events].count("DELETE") == 1
            assert [event["operation"] for event in events].count("CREATE") == 3
    finally:
        provider_module.provider_sessions.delete(
            old_session_id if "old_session_id" in locals() else None
        )
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
