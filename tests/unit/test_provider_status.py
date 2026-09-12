from fastapi.testclient import TestClient

from research_agent.api.app import create_app
from research_agent.application.provider_session import ProviderSessionStore
from research_agent.config.settings import get_settings


def test_provider_status_does_not_expose_bearer_token(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    monkeypatch.setenv("MODEL_ID", "au.anthropic.claude-sonnet-4-6")
    monkeypatch.setenv("AWS_REGION", "ap-southeast-2")
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "temporary-secret")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            response = client.get("/provider/status")
            assert response.status_code == 200
            payload = response.json()
            assert payload["provider"] == "bedrock"
            assert payload["model_id"] == "au.anthropic.claude-sonnet-4-6"
            assert payload["region"] == "ap-southeast-2"
            assert payload["credential_mode"] == "bearer_token"
            assert "temporary-secret" not in response.text
    finally:
        monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        monkeypatch.delenv("MODEL_ID", raising=False)
        monkeypatch.delenv("AWS_REGION", raising=False)
        get_settings.cache_clear()


def test_provider_panel_is_credential_safe() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/provider")
        assert response.status_code == 200
        assert "fetch('/provider/status')" in response.text
        assert "AWS_BEARER_TOKEN_BEDROCK" not in response.text
        assert "Credential values are never returned" in response.text


def test_provider_session_is_cookie_scoped_and_not_returned(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            created = client.post(
                "/provider/session",
                json={"bearer_token": "temporary-secret", "ttl_seconds": 600},
            )
            assert created.status_code == 201
            assert "temporary-secret" not in created.text
            status = client.get("/provider/status")
            assert status.json()["credential_mode"] == "session_bearer_token"
            deleted = client.delete("/provider/session")
            assert deleted.status_code == 204
            assert client.get("/provider/status").json()["credential_mode"] == "aws_default_chain"
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        get_settings.cache_clear()


def test_provider_session_is_disabled_outside_local_by_default(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    monkeypatch.setenv("ENVIRONMENT", "production")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            response = client.post(
                "/provider/session",
                json={"bearer_token": "temporary-secret", "ttl_seconds": 600},
            )
            assert response.status_code == 404
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        get_settings.cache_clear()


def test_provider_session_rejects_cross_origin_request(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            response = client.post(
                "/provider/session",
                headers={"origin": "https://evil.example"},
                json={"bearer_token": "temporary-secret", "ttl_seconds": 600},
            )
            assert response.status_code == 403
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        get_settings.cache_clear()


def test_provider_session_accepts_loopback_origin_with_port(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            response = client.post(
                "/provider/session",
                headers={"origin": "http://localhost:8000"},
                json={"bearer_token": "temporary-secret", "ttl_seconds": 600},
            )
            assert response.status_code == 201
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        get_settings.cache_clear()


def test_provider_session_store_bounds_live_sessions():
    store = ProviderSessionStore(max_sessions=1)
    first_id, _ = store.create("first", 600)
    second_id, _ = store.create("second", 600)

    assert store.get(first_id) is None
    assert store.get(second_id) == "second"
