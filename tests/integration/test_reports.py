from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from research_agent.api.app import create_app
from research_agent.config.settings import get_settings
from research_agent.persistence.database import engine
from research_agent.persistence.models import ResearchTaskRecord


def test_report_is_read_only_and_keeps_provenance_links() -> None:
    with TestClient(create_app()) as client:
        created = client.post(
            "/investigations",
            json={
                "title": "Report test",
                "objective": "Build an evidence inventory.",
                "hypotheses": [{"label": "H1", "statement": "Evidence exists."}],
            },
        )
        assert created.status_code == 201
        task = created.json()["task"]
        task_id = UUID(task["id"])
        try:
            source = client.post(
                f"/investigations/{task['id']}/sources",
                json={
                    "source_type": "document",
                    "title": "A source",
                    "content": "A source statement.",
                },
            )
            assert source.status_code == 201
            claim = client.post(
                f"/investigations/{task['id']}/claims",
                json={
                    "statement": "Evidence exists.",
                    "source_links": [
                        {"source_id": source.json()["id"], "support_type": "supporting"}
                    ],
                },
            )
            assert claim.status_code == 201

            report = client.get(f"/investigations/{task['id']}/report")
            assert report.status_code == 200, report.text
            payload = report.json()
            assert payload["task_id"] == task["id"]
            assert payload["sources"][0]["id"] == source.json()["id"]
            assert payload["claims"][0]["source_links"][0]["source_id"] == source.json()["id"]
            assert "content" not in payload["sources"][0]
            assert payload["hypotheses"][0]["assessment_status"] is None
        finally:
            with engine.begin() as connection:
                connection.execute(
                    delete(ResearchTaskRecord).where(ResearchTaskRecord.id == task_id)
                )


def test_report_draft_is_generated_without_persisting_state() -> None:
    with TestClient(create_app()) as client:
        created = client.post(
            "/investigations",
            json={"title": "Draft test", "objective": "Keep uncertainty visible."},
        )
        assert created.status_code == 201
        task = created.json()["task"]
        task_id = UUID(task["id"])
        try:
            before = client.get(f"/investigations/{task['id']}").json()
            draft = client.post(f"/investigations/{task['id']}/report/draft")
            assert draft.status_code == 200, draft.text
            assert draft.json()["provider"] == "rule_based"
            assert "does not establish conclusions" in draft.json()["content"]
            events = client.get(f"/investigations/{task['id']}/events").json()
            generated = [
                event for event in events if event["event_type"] == "report.draft_generated"
            ]
            assert len(generated) == 1
            assert generated[0]["payload"]["claim_count"] == 0
            assert "content" not in generated[0]["payload"]
            after = client.get(f"/investigations/{task['id']}").json()
            assert after == before
        finally:
            with engine.begin() as connection:
                connection.execute(
                    delete(ResearchTaskRecord).where(ResearchTaskRecord.id == task_id)
                )


def test_report_draft_budget_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MAX_DRAFTS_PER_TASK", "0")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            created = client.post(
                "/investigations",
                json={"title": "Budget test", "objective": "Bound draft usage."},
            )
            assert created.status_code == 201
            task = created.json()["task"]
            task_id = UUID(task["id"])
            try:
                response = client.post(f"/investigations/{task['id']}/report/draft")
                assert response.status_code == 429
                events = client.get(f"/investigations/{task['id']}/events").json()
                assert events[-1]["payload"]["reason"] == "report_budget_exceeded"
            finally:
                with engine.begin() as connection:
                    connection.execute(
                        delete(ResearchTaskRecord).where(ResearchTaskRecord.id == task_id)
                    )
    finally:
        monkeypatch.delenv("LLM_MAX_DRAFTS_PER_TASK", raising=False)
        get_settings.cache_clear()


def test_investigation_workspace_is_credential_free() -> None:
    task_id = "00000000-0000-0000-0000-000000000001"
    with TestClient(create_app()) as client:
        response = client.get(f"/investigations/{task_id}/workspace")
        assert response.status_code == 200
        assert "/report" in response.text
        assert "AWS_BEARER_TOKEN_BEDROCK" not in response.text
        assert "Generate draft" in response.text
        assert "Run local agent cycle" in response.text
        assert "Agent comparisons" in response.text
