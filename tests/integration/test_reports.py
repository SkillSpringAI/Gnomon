from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from conftest import purge_test_tasks
from fastapi.testclient import TestClient

from research_agent.api.app import create_app
from research_agent.application.provider_budget_service import (
    ProviderBudgetExceeded,
    ProviderBudgetService,
)
from research_agent.config.settings import get_settings
from research_agent.persistence.database import SessionFactory, engine
from research_agent.persistence.models import ReportGenerationAttemptRecord


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
                purge_test_tasks(connection, [task_id])


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
                purge_test_tasks(connection, [task_id])


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
                    purge_test_tasks(connection, [task_id])
    finally:
        monkeypatch.delenv("LLM_MAX_DRAFTS_PER_TASK", raising=False)
        get_settings.cache_clear()


def test_report_budget_allows_only_one_concurrent_reservation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_MAX_DRAFTS_PER_TASK", "1")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            task = client.post(
                "/investigations", json={"title": "Concurrent budget", "objective": "Bound usage."}
            ).json()["task"]
            task_id = UUID(task["id"])
            try:
                operation_ids = iter((UUID(int=4), UUID(int=5)))

                def generate() -> int:
                    return client.post(
                        f"/investigations/{task_id}/report/draft",
                        headers={"Idempotency-Key": str(next(operation_ids))},
                    ).status_code

                with ThreadPoolExecutor(max_workers=2) as pool:
                    statuses = sorted(pool.map(lambda _: generate(), range(2)))
                assert statuses == [200, 429]
            finally:
                with engine.begin() as connection:
                    purge_test_tasks(connection, [task_id])
    finally:
        monkeypatch.delenv("LLM_MAX_DRAFTS_PER_TASK", raising=False)
        get_settings.cache_clear()


def test_expired_pending_reservation_releases_capacity() -> None:
    with TestClient(create_app()) as client:
        task = client.post(
            "/investigations", json={"title": "Expiry", "objective": "Recover capacity."}
        ).json()["task"]
        task_id = UUID(task["id"])
        try:
            expired_id = UUID(int=2)
            with SessionFactory() as session:
                session.add(
                    ReportGenerationAttemptRecord(
                        operation_id=expired_id,
                        task_id=task_id,
                        status="PENDING",
                        started_at=datetime.now(UTC) - timedelta(minutes=10),
                        expires_at=datetime.now(UTC) - timedelta(minutes=5),
                    )
                )
                session.commit()
                reserved = ProviderBudgetService(session).reserve(task_id, UUID(int=3), 1, 30)
                assert reserved.status == "PENDING"
                expired = session.get(ReportGenerationAttemptRecord, expired_id)
                assert expired is not None and expired.status == "EXPIRED"
        finally:
            with engine.begin() as connection:
                purge_test_tasks(connection, [task_id])


def test_dispatched_attempt_cannot_be_expired_or_refunded() -> None:
    with TestClient(create_app()) as client:
        task = client.post(
            "/investigations", json={"title": "Dispatched", "objective": "Keep in-flight work."}
        ).json()["task"]
        task_id = UUID(task["id"])
        try:
            first_id, second_id = UUID(int=6), UUID(int=7)
            with SessionFactory() as first, SessionFactory() as second:
                ProviderBudgetService(first).reserve(task_id, first_id, 1, 1)
                ProviderBudgetService(first).dispatch(first_id)
                with pytest.raises(ProviderBudgetExceeded):
                    ProviderBudgetService(second).reserve(task_id, second_id, 1, 1)
                current = first.get(ReportGenerationAttemptRecord, first_id)
                assert current is not None and current.status == "DISPATCHED"
        finally:
            with engine.begin() as connection:
                purge_test_tasks(connection, [task_id])


def test_investigation_workspace_is_credential_free() -> None:
    with TestClient(create_app()) as client:
        created = client.post(
            "/investigations",
            json={"title": "Workspace", "objective": "Render the workspace."},
        )
        task_id = created.json()["task"]["id"]
        response = client.get(f"/investigations/{task_id}/workspace")
        assert response.status_code == 200
        assert "/report" in response.text
        assert "AWS_BEARER_TOKEN_BEDROCK" not in response.text
        assert "Generate draft" in response.text
        assert "Run local agent cycle" in response.text
        assert "Agent comparisons" in response.text
        with engine.begin() as connection:
            purge_test_tasks(connection, [UUID(task_id)])


def test_unknown_investigation_workspace_is_not_served() -> None:
    with TestClient(create_app()) as client:
        response = client.get(
            "/investigations/00000000-0000-0000-0000-000000000001/workspace"
        )
        assert response.status_code == 404
