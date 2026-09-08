"""Durability, transaction, isolation, and data-minimization audit contracts."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, func, select

from research_agent.adapters.web.http import SourceRetrievalError
from research_agent.api.app import create_app
from research_agent.api.routes.evidence import get_source_retriever
from research_agent.application.claim_extraction_service import ClaimExtractionService
from research_agent.application.evidence_service import EvidenceService
from research_agent.application.source_registry import UntrustedSourceError
from research_agent.domain.research import (
    ClaimCreate,
    ClaimSourceLink,
    SourceCreate,
    SourceType,
    SupportType,
)
from research_agent.persistence.database import SessionFactory, engine
from research_agent.persistence.models import (
    ResearchClaimRecord,
    ResearchEventRecord,
    ResearchSourceRecord,
    ResearchTaskRecord,
)


@pytest.fixture
def audit_task():
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/investigations",
            json={
                "title": "Audit contract",
                "objective": "Inspect durable operation outcomes.",
            },
        )
        assert response.status_code == 201
        task_id = response.json()["task"]["id"]
        try:
            yield app, client, task_id
        finally:
            with engine.begin() as connection:
                connection.execute(
                    delete(ResearchTaskRecord).where(ResearchTaskRecord.id == UUID(task_id))
                )


def create_source(client, task_id):
    response = client.post(
        f"/investigations/{task_id}/sources",
        json={
            "source_type": "document",
            "title": "SECRET_TITLE",
            "uri": "https://user:SECRET_PASSWORD@example.test/path?token=SECRET_TOKEN",
            "content": "SECRET_BODY first observation. Another observation.",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_audit_survives_fresh_app_and_correlates_extraction(audit_task, monkeypatch):
    from research_agent.application import audit_service

    fixed_time = audit_service.utc_now()
    monkeypatch.setattr(audit_service, "utc_now", lambda: fixed_time)
    _, client, task_id = audit_task
    assert client.get(f"/investigations/{task_id}/events").json() == []
    source = create_source(client, task_id)
    assert create_source(client, task_id) == source
    extraction_url = f"/investigations/{task_id}/sources/{source['id']}/extract-claims"
    first = client.post(extraction_url)
    assert first.status_code == 200, first.text
    assert client.post(extraction_url).json() == first.json()
    with TestClient(create_app()) as fresh:
        response = fresh.get(f"/investigations/{task_id}/events")
        assert response.status_code == 200, response.text
        events = response.json()
        assert [item["event_type"] for item in events] == [
            "source.created",
            "source.reused",
            "claim.created",
            "claim.created",
            "extraction.completed",
            "claim.reused",
            "claim.reused",
            "extraction.completed",
        ]
        assert len({item["payload"]["operation_id"] for item in events[2:5]}) == 1
        assert len({item["payload"]["operation_id"] for item in events[5:]}) == 1
        assert events[4]["payload"]["operation_id"] != events[-1]["payload"]["operation_id"]
        assert events[4]["payload"]["claim_count"] == 2
        assert all(item["task_id"] == task_id for item in events)
        assert "SECRET" not in response.text
        assert "https://" not in response.text
        assert fresh.get(f"/investigations/{task_id}/events?limit=2&offset=2").json() == events[2:4]
        assert fresh.get(f"/investigations/{task_id}/events?limit=101").status_code == 422
        assert fresh.get(f"/investigations/{task_id}/events?offset=-1").status_code == 422
        assert fresh.get(f"/investigations/{uuid4()}/events").status_code == 404
        other = fresh.post("/investigations", json={"title": "Other", "objective": "Isolation."})
        other_id = UUID(other.json()["task"]["id"])
        try:
            assert fresh.get(f"/investigations/{other_id}/events").json() == []
        finally:
            with engine.begin() as connection:
                connection.execute(
                    delete(ResearchTaskRecord).where(ResearchTaskRecord.id == other_id)
                )


def test_failed_extraction_has_failure_event_without_partial_success(audit_task):
    _, client, task_id = audit_task
    source = create_source(client, task_id)

    class InvalidBatch:
        def extract(self, source):
            return [
                ClaimCreate(
                    statement="SECRET_PROPOSAL",
                    source_links=[
                        ClaimSourceLink(
                            source_id=source.id,
                            support_type=SupportType.SUPPORTING,
                        )
                    ],
                ),
                ClaimCreate(
                    statement="SECRET_INVALID",
                    source_links=[
                        ClaimSourceLink(
                            source_id=uuid4(),
                            support_type=SupportType.SUPPORTING,
                        )
                    ],
                ),
            ]

    with SessionFactory() as session:
        with pytest.raises(ValueError):
            ClaimExtractionService(session, InvalidBatch()).extract_for_source(
                UUID(task_id),
                UUID(source["id"]),
            )
        assert (
            session.scalar(
                select(func.count())
                .select_from(ResearchClaimRecord)
                .where(
                    ResearchClaimRecord.task_id == UUID(task_id),
                )
            )
            == 0
        )
    response = client.get(f"/investigations/{task_id}/events")
    assert [row["event_type"] for row in response.json()] == ["source.created", "extraction.failed"]
    assert response.json()[-1]["payload"]["reason"] == "extraction_failed"
    assert "SECRET" not in response.text


@pytest.mark.parametrize(
    "failure, status, reason",
    [
        (SourceRetrievalError("SECRET_PROVIDER_ERROR"), 422, "retrieval_rejected"),
        (UntrustedSourceError("SECRET_REGISTRY_ERROR"), 403, "domain_not_enabled"),
    ],
)
def test_retrieval_failures_are_durable_and_redacted(audit_task, failure, status, reason):
    app, client, task_id = audit_task

    class RejectRetriever:
        def fetch(self, target):
            raise failure

    app.dependency_overrides[get_source_retriever] = RejectRetriever
    response = client.post(
        f"/investigations/{task_id}/sources/fetch",
        json={
            "uri": "https://SECRET_USER:SECRET_PASSWORD@example.test/SECRET_PATH?token=SECRET_TOKEN",
        },
    )
    assert response.status_code == status
    events = client.get(f"/investigations/{task_id}/events")
    assert "SECRET" not in events.text
    assert len(events.json()) == 1
    assert events.json()[0]["event_type"] == "retrieval.failed"
    assert events.json()[0]["payload"]["reason"] == reason
    assert client.get(f"/investigations/{task_id}/snapshot").json()["sources"] == []
    assert (
        client.post(
            f"/investigations/{uuid4()}/sources/fetch",
            json={
                "uri": "https://example.test",
            },
        ).status_code
        == 404
    )
    assert client.get(f"/investigations/{task_id}/events").json() == events.json()


def test_event_insert_failure_rolls_back_source_write(audit_task):
    _, client, task_id = audit_task

    def reject_event(*args):
        raise RuntimeError("Simulated event storage failure")

    event.listen(ResearchEventRecord, "before_insert", reject_event)
    try:
        with SessionFactory() as session:
            with pytest.raises(RuntimeError, match="event storage"):
                EvidenceService(session).create_source(
                    UUID(task_id),
                    SourceCreate(
                        source_type=SourceType.DOCUMENT,
                        title="Test",
                        content="Must roll back.",
                    ),
                )
    finally:
        event.remove(ResearchEventRecord, "before_insert", reject_event)
    with engine.connect() as connection:
        assert (
            connection.scalar(
                select(func.count())
                .select_from(ResearchSourceRecord)
                .where(
                    ResearchSourceRecord.task_id == UUID(task_id),
                )
            )
            == 0
        )
    assert client.get(f"/investigations/{task_id}/events").json() == []
