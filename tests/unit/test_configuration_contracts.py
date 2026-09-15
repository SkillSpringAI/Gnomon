"""Exercise configuration-driven composition rather than injected repositories."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from research_agent.api.app import create_app
from research_agent.config.settings import get_settings
from research_agent.domain.events import EventPayload


@pytest.fixture(autouse=True)
def clear_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_memory_backend_lives_for_one_application(monkeypatch):
    monkeypatch.setenv("PERSISTENCE_BACKEND", "memory")
    with TestClient(create_app()) as first, TestClient(create_app()) as second:
        response = first.post(
            "/investigations", json={"title": "Memory", "objective": "Keep tasks."}
        )
        assert response.status_code == 201
        task_id = response.json()["task"]["id"]
        assert first.get(f"/investigations/{task_id}").status_code == 200
        started = first.post(f"/investigations/{task_id}/cycles/1/start")
        assert started.status_code == 200, started.text
        assert (
            first.get(f"/investigations/{task_id}").json()["task"]["cycles"][0]["status"]
            == "active"
        )
        assert second.get(f"/investigations/{task_id}").status_code == 404


@pytest.mark.parametrize(
    "setting,value",
    [
        ("LLM_PROVIDER", "misspelled"),
        ("LLM_TIMEOUT_SECONDS", "0"),
        ("LLM_MAX_OUTPUT_TOKENS", "0"),
        ("LLM_MAX_REPORT_CHARS", "-1"),
        ("LLM_MAX_DRAFTS_PER_TASK", "-1"),
    ],
)
def test_invalid_provider_settings_fail_at_app_construction(monkeypatch, setting, value):
    monkeypatch.setenv(setting, value)
    with pytest.raises(ValidationError):
        create_app()


def test_disabled_draft_budget_is_visible_in_provider_status(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", " STUB ")
    monkeypatch.setenv("LLM_MAX_DRAFTS_PER_TASK", "0")
    with TestClient(create_app()) as client:
        response = client.get("/provider/status")
        assert response.status_code == 200
        assert response.json()["max_drafts_per_task"] == 0
        assert response.json()["provider"] == "stub"


def test_public_reason_contract_rejects_arbitrary_prose():
    with pytest.raises(ValidationError):
        EventPayload(
            operation_id="00000000-0000-0000-0000-000000000001",
            change_reason="Private operator notes https://private.test secret=example",
        )
