"""Retry and concurrency contracts for PostgreSQL evidence writes."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from research_agent.adapters.llm.rule_based import RuleBasedClaimExtractor
from research_agent.api.app import create_app
from research_agent.application.claim_extraction_service import ClaimExtractionService
from research_agent.domain.research import ClaimCreate, ClaimSourceLink, SupportType
from research_agent.persistence.database import SessionFactory, engine
from research_agent.persistence.models import ResearchClaimRecord, ResearchTaskRecord


@pytest.fixture
def task_ids():
    ids = []
    try:
        yield ids
    finally:
        with engine.begin() as connection:
            connection.execute(delete(ResearchTaskRecord).where(ResearchTaskRecord.id.in_(ids)))


def new_task(client, ids):
    response = client.post(
        "/investigations",
        json={
            "title": "Retry contract",
            "objective": "Keep retries from duplicating evidence.",
        },
    )
    assert response.status_code == 201, response.text
    task_id = response.json()["task"]["id"]
    ids.append(UUID(task_id))
    return task_id


def source_payload(**changes):
    return {
        "source_type": "document",
        "title": "Original",
        "uri": "https://example.test/evidence",
        "content": "First observation. Second observation.",
        "reliability_score": 0.4,
    } | changes


def ingest(client, task_id, payload):
    response = client.post(f"/investigations/{task_id}/sources", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize("uri", [None, "https://example.test/evidence"])
def test_source_retry_preserves_original_and_distinct_provenance(task_ids, uri):
    with TestClient(create_app()) as client:
        task_id = new_task(client, task_ids)
        payload = source_payload(uri=uri)
        original = ingest(client, task_id, payload)
        retry = ingest(
            client, task_id, payload | {"title": "Changed title", "reliability_score": 0.9}
        )
        assert retry == original
        changed = ingest(client, task_id, payload | {"content": "New observation."})
        other_origin = ingest(client, task_id, payload | {"uri": "https://other.test/evidence"})
        other_type = ingest(client, task_id, payload | {"source_type": "user_statement"})
        other_task = ingest(client, new_task(client, task_ids), payload)
        assert (
            len({item["id"] for item in [original, changed, other_origin, other_type, other_task]})
            == 5
        )
    with TestClient(create_app()) as fresh:
        assert ingest(fresh, task_id, payload) == original
        assert len(fresh.get(f"/investigations/{task_id}/snapshot").json()["sources"]) == 4


def test_claim_retry_ignores_link_order_and_preserves_saved_judgments(task_ids):
    with TestClient(create_app()) as client:
        task_id = new_task(client, task_ids)
        first = ingest(client, task_id, source_payload())
        second = ingest(client, task_id, source_payload(uri="https://second.test"))
        payload = {
            "statement": "A proposition.",
            "confidence": 0.2,
            "source_links": [
                {"source_id": first["id"], "support_type": "supporting", "strength": 0.3},
                {"source_id": second["id"], "support_type": "context", "strength": 0.4},
            ],
        }
        url = f"/investigations/{task_id}/claims"
        initial = client.post(url, json=payload)
        assert initial.status_code == 201
        retry_payload = payload | {
            "confidence": 0.99,
            "status": "supported",
            "source_links": [
                link | {"strength": 0.99} for link in reversed(payload["source_links"])
            ],
        }
        assert client.post(url, json=retry_payload).json() == initial.json()
        changed_relation = payload | {
            "source_links": [
                payload["source_links"][0] | {"support_type": "contradicting"},
                payload["source_links"][1],
            ]
        }
        distinct = client.post(url, json=changed_relation)
        assert distinct.status_code == 201
        assert distinct.json()["id"] != initial.json()["id"]
        duplicate_link = payload | {"source_links": [payload["source_links"][0]] * 2}
        assert client.post(url, json=duplicate_link).status_code == 422
        assert len(client.get(f"/investigations/{task_id}/snapshot").json()["claims"]) == 2


def test_concurrent_ingestion_and_extraction_return_same_records(task_ids):
    with TestClient(create_app()) as client:
        task_id = new_task(client, task_ids)
    barrier = Barrier(2)

    def ingest_concurrently():
        with TestClient(create_app()) as client:
            barrier.wait(timeout=5)
            return ingest(client, task_id, source_payload())

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: ingest_concurrently(), range(2)))
    assert results[0] == results[1]
    source_id = results[0]["id"]
    url = f"/investigations/{task_id}/sources/{source_id}/extract-claims"

    def extract_concurrently():
        with TestClient(create_app()) as client:
            barrier.wait(timeout=5)
            response = client.post(url)
            assert response.status_code == 200, response.text
            return response.json()

    with ThreadPoolExecutor(max_workers=2) as workers:
        claims = list(workers.map(lambda _: extract_concurrently(), range(2)))
    assert claims[0] == claims[1]
    assert len(claims[0]) == 2
    with TestClient(create_app()) as client:
        assert client.post(url).json() == claims[0]
        snapshot = client.get(f"/investigations/{task_id}/snapshot").json()
        assert len(snapshot["sources"]) == 1
        assert len(snapshot["claims"]) == 2
        events = client.get(f"/investigations/{task_id}/events").json()
        types = [row["event_type"] for row in events]
        assert types.count("source.created") == 1
        assert types.count("source.reused") == 1
        assert types.count("claim.created") == 2
        assert types.count("claim.reused") == 4
        assert types.count("extraction.completed") == 3
        assert all(len(claim["source_links"]) == 1 for claim in snapshot["claims"])


def test_extraction_failure_rolls_back_whole_batch_and_can_retry(task_ids):
    with TestClient(create_app()) as client:
        task_id = new_task(client, task_ids)
        source = ingest(client, task_id, source_payload())

    class InvalidSecondProposal:
        def extract(self, source):
            proposals = RuleBasedClaimExtractor().extract(source)
            return [
                proposals[0],
                ClaimCreate(
                    statement="Invalid provenance.",
                    source_links=[
                        ClaimSourceLink(
                            source_id=uuid4(),
                            support_type=SupportType.SUPPORTING,
                        )
                    ],
                ),
            ]

    with SessionFactory() as session:
        with pytest.raises(ValueError, match="requested source"):
            ClaimExtractionService(session, InvalidSecondProposal()).extract_for_source(
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
        result = ClaimExtractionService(session).extract_for_source(
            UUID(task_id), UUID(source["id"])
        )
        assert len(result) == 2
        assert (
            ClaimExtractionService(session).extract_for_source(
                UUID(task_id),
                UUID(source["id"]),
            )
            == result
        )


def test_repeated_sentences_create_one_claim(task_ids):
    with TestClient(create_app()) as client:
        task_id = new_task(client, task_ids)
        source = ingest(
            client, task_id, source_payload(content="Same observation. Same observation.")
        )
        url = f"/investigations/{task_id}/sources/{source['id']}/extract-claims"
        response = client.post(url)
        assert response.status_code == 200, response.text
        assert len(response.json()) == 1
        assert client.post(url).json() == response.json()
