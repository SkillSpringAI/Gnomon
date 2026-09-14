"""PostgreSQL contracts for reading a complete, isolated evidence chain."""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from conftest import purge_test_tasks
from fastapi.testclient import TestClient
from sqlalchemy import delete, text

from research_agent.api.app import create_app
from research_agent.persistence.database import engine


@pytest.fixture
def investigations() -> Iterator[tuple[TestClient, list[str]]]:
    # Unlike the older smoke tests, a missing database fails this persistence contract.
    with engine.connect() as connection:
        connection.execute(text("SELECT 1 FROM hypothesis_assessments LIMIT 1"))
    ids: list[str] = []
    with TestClient(create_app()) as client:
        try:
            yield client, ids
        finally:
            with engine.begin() as connection:
                purge_test_tasks(connection, [UUID(task_id) for task_id in ids])


def create_task(client: TestClient, ids: list[str], *, hypotheses: bool = True) -> dict:
    response = client.post(
        "/investigations",
        json={
            "title": "Snapshot contract",
            "objective": "Compare the evidence for adaptation.",
            "hypotheses": [
                {"label": "H1", "statement": "Adaptation is uneven."},
                {"label": "H2", "statement": "Governance affects outcomes."},
            ]
            if hypotheses
            else [],
            "questions": [{"question": "What evidence would change the assessment?"}],
        },
    )
    assert response.status_code == 201, response.text
    task = response.json()["task"]
    ids.append(task["id"])
    return task


def add_evidence(client: TestClient, task_id: str, relation: str) -> tuple[dict, dict]:
    source = client.post(
        f"/investigations/{task_id}/sources",
        json={
            "source_type": "document",
            "title": f"{relation} evidence",
            "uri": f"https://example.org/{relation}",
            "publisher": "Test publisher",
            "content": f"Stored {relation} source text.",
            "reliability_score": 0.6,
        },
    )
    assert source.status_code == 201, source.text
    claim = client.post(
        f"/investigations/{task_id}/claims",
        json={
            "statement": f"An unverified {relation} proposition.",
            "confidence": 0.2,
            "source_links": [
                {
                    "source_id": source.json()["id"],
                    "support_type": relation,
                    "strength": 0.3,
                }
            ],
        },
    )
    assert claim.status_code == 201, claim.text
    return source.json(), claim.json()


def test_snapshot_recovers_evidence_from_fresh_app(investigations: tuple) -> None:
    client, ids = investigations
    task = create_task(client, ids)
    task_id = task["id"]
    first_source, first_claim = add_evidence(client, task_id, "supporting")
    second_source, second_claim = add_evidence(client, task_id, "contradicting")
    foreign = create_task(client, ids)
    foreign_source, foreign_claim = add_evidence(client, foreign["id"], "supporting")
    assessment_url = (
        f"/investigations/{task_id}/hypotheses/{task['brief']['hypotheses'][0]['id']}/assessment"
    )
    payload = {
        "status": "supported",
        "summary": "Initial assessment.",
        "confidence": 0.4,
        "evidence_links": [
            {
                "claim_id": first_claim["id"],
                "relation": "supporting",
                "strength": 0.4,
            }
        ],
    }
    initial = client.put(assessment_url, json=payload)
    assert initial.status_code == 200, initial.text
    payload.update(status="mixed", summary="Counterevidence leaves uncertainty.", confidence=0.35)
    payload["evidence_links"].append(
        {
            "claim_id": second_claim["id"],
            "relation": "contradicting",
            "strength": 0.5,
        }
    )
    updated = client.put(assessment_url, json=payload)
    assert updated.status_code == 200, updated.text

    with TestClient(create_app()) as fresh:
        response = fresh.get(f"/investigations/{task_id}/snapshot")
        assert response.status_code == 200, response.text
        snapshot = response.json()
        assert fresh.get(f"/investigations/{task_id}/snapshot").json() == snapshot
    assert snapshot["task"] == task
    assert snapshot["open_questions"] == task["plan"]["open_questions"]
    assessed, missing = snapshot["hypotheses"]
    assert assessed["assessment_state"] == "assessed"
    assert assessed["assessment"]["id"] == initial.json()["id"]
    assert assessed["assessment"]["status"] == "mixed"
    assert assessed["assessment"]["confidence"] == 0.35
    assert assessed["assessment"]["summary"] == payload["summary"]
    assert {link["relation"] for link in assessed["assessment"]["evidence_links"]} == {
        "supporting",
        "contradicting",
    }
    assert missing["assessment_state"] == "not_assessed"
    assert missing["assessment"] is None
    assert snapshot["claims"] == [first_claim, second_claim]
    assert snapshot["sources"] == [first_source, second_source]
    assert foreign_source["id"] not in response.text
    assert foreign_claim["id"] not in response.text


def test_snapshot_without_evidence(investigations: tuple) -> None:
    client, ids = investigations
    task = create_task(client, ids)
    response = client.get(f"/investigations/{task['id']}/snapshot")
    assert response.status_code == 200
    snapshot = response.json()
    assert snapshot["sources"] == snapshot["claims"] == []
    assert all(row["assessment_state"] == "not_assessed" for row in snapshot["hypotheses"])
    assert all(row["assessment"] is None for row in snapshot["hypotheses"])
    empty = create_task(client, ids, hypotheses=False)
    assert client.get(f"/investigations/{empty['id']}/snapshot").json()["hypotheses"] == []
    assert client.get(f"/investigations/{uuid4()}/snapshot").status_code == 404
    assert client.get("/investigations/not-a-uuid/snapshot").status_code == 422


def test_foreign_evidence_is_rejected(investigations: tuple) -> None:
    client, ids = investigations
    task = create_task(client, ids)
    foreign = create_task(client, ids)
    source, claim = add_evidence(client, foreign["id"], "supporting")
    rejected_claim = client.post(
        f"/investigations/{task['id']}/claims",
        json={
            "statement": "Must not cross investigations.",
            "source_links": [{"source_id": source["id"], "support_type": "supporting"}],
        },
    )
    assert rejected_claim.status_code == 422
    rejected_assessment = client.put(
        f"/investigations/{task['id']}/hypotheses/{task['brief']['hypotheses'][0]['id']}/assessment",
        json={
            "status": "supported",
            "summary": "Must not cross investigations.",
            "evidence_links": [{"claim_id": claim["id"], "relation": "supporting"}],
        },
    )
    assert rejected_assessment.status_code == 422
    snapshot = client.get(f"/investigations/{task['id']}/snapshot").json()
    assert snapshot["claims"] == snapshot["sources"] == []
    assert snapshot["hypotheses"][0]["assessment"] is None


@pytest.mark.parametrize(
    "mode, expected_status",
    [
        ("approved", 201),
        ("unapproved_redirect", 403),
        ("pdf", 422),
        ("oversized", 422),
    ],
)
def test_fetch_policy_and_persistence(
    investigations: tuple,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    expected_status: int,
) -> None:
    import httpx

    from research_agent.adapters.web.http import HttpSourceRetriever
    from research_agent.api.routes import evidence
    from research_agent.config.settings import get_settings
    from research_agent.persistence.models import TrustedSourceRecord

    client, ids = investigations
    task = create_task(client, ids)
    domain = f"approved-{uuid4().hex}.test"
    contacted = []

    def handler(request: httpx.Request) -> httpx.Response:
        contacted.append(str(request.url))
        if request.url.path == "/start":
            destination = "unapproved.test" if mode == "unapproved_redirect" else domain
            return httpx.Response(302, headers={"location": f"https://{destination}/paper"})
        if mode == "pdf":
            return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF")
        if mode == "oversized":
            return httpx.Response(200, headers={"content-type": "text/plain"}, content=b"a" * 501)
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<title>Evidence</title><p>Observed result.</p><script>ignore this</script>",
        )

    def retriever_factory(**kwargs):
        return HttpSourceRetriever(
            httpx.Client(transport=httpx.MockTransport(handler)),
            max_bytes=500,
            **kwargs,
        )

    monkeypatch.setattr(evidence, "HttpSourceRetriever", retriever_factory)
    monkeypatch.setattr(get_settings(), "require_trusted_sources", True)
    try:
        registration = client.post(
            "/source-registry",
            json={
                "domain": domain,
                "display_name": "Test source",
                "verification_method": "Test review",
            },
        )
        assert registration.status_code == 201, registration.text
        enabled = client.post(f"/source-registry/{domain}/enable")
        assert enabled.status_code == 200, enabled.text
        response = client.post(
            f"/investigations/{task['id']}/sources/fetch",
            json={"uri": f"https://{domain}/start"},
        )
        assert response.status_code == expected_status, response.text
        snapshot = client.get(f"/investigations/{task['id']}/snapshot").json()
        if mode == "approved":
            retry = client.post(
                f"/investigations/{task['id']}/sources/fetch",
                json={"uri": f"https://{domain}/start"},
            )
            assert retry.status_code == 201
            assert retry.json() == response.json()
            assert len(client.get(f"/investigations/{task['id']}/snapshot").json()["sources"]) == 1
            assert snapshot["sources"][0]["content"] == "Observed result."
            assert snapshot["sources"][0]["uri"] == f"https://{domain}/paper"
            assert snapshot["sources"][0]["title"] == "Evidence"
        else:
            assert snapshot["sources"] == []
        assert all(httpx.URL(uri).host == domain for uri in contacted)
        before = len(contacted)
        missing = client.post(
            f"/investigations/{uuid4()}/sources/fetch",
            json={"uri": f"https://{domain}/start"},
        )
        assert missing.status_code == 404
        assert len(contacted) == before
    finally:
        with engine.begin() as connection:
            connection.execute(
                delete(TrustedSourceRecord).where(TrustedSourceRecord.domain == domain)
            )
