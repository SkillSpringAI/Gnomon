import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from research_agent.api.app import app

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://research_agent:research_agent@localhost:5432/research_agent",
)


def test_api_uses_postgres_backend() -> None:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1 FROM research_tasks LIMIT 1"))
    except Exception as exc:  # pragma: no cover - environment-dependent skip
        pytest.skip(f"PostgreSQL schema is unavailable: {exc}")

    client = TestClient(app)
    response = client.post(
        "/investigations",
        json={
            "title": "API persistence test",
            "objective": "Verify that the configured API backend is PostgreSQL.",
            "hypotheses": [
                {
                    "label": "H1",
                    "statement": "Institutional adaptation is uneven.",
                }
            ],
            "questions": [{"question": "Does the task survive the request?"}],
        },
    )

    assert response.status_code == 201
    task = response.json()["task"]
    task_id = task["id"]
    retrieved = client.get(f"/investigations/{task_id}")
    assert retrieved.status_code == 200
    assert retrieved.json()["task"]["id"] == task_id

    source = client.post(
        f"/investigations/{task_id}/sources",
        json={
            "source_type": "web_page",
            "title": "Example evidence",
            "uri": "https://example.com/evidence",
            "publisher": "Example Publisher",
            "content": "Institutions often adapt at different speeds.",
            "reliability_score": 0.7,
        },
    )
    assert source.status_code == 201
    source_id = source.json()["id"]

    claim = client.post(
        f"/investigations/{task_id}/claims",
        json={
            "statement": "Institutional adaptation can be uneven.",
            "confidence": 0.6,
            "source_links": [
                {
                    "source_id": source_id,
                    "support_type": "supporting",
                    "strength": 0.8,
                }
            ],
        },
    )
    assert claim.status_code == 201
    claim_id = claim.json()["id"]
    assert claim.json()["source_links"][0]["source_id"] == source_id

    hypothesis_id = task["brief"]["hypotheses"][0]["id"]
    assessment = client.put(
        f"/investigations/{task_id}/hypotheses/{hypothesis_id}/assessment",
        json={
            "status": "supported",
            "summary": "The stored claim provides limited support for the hypothesis.",
            "confidence": 0.4,
            "evidence_links": [
                {
                    "claim_id": claim_id,
                    "relation": "supporting",
                    "strength": 0.4,
                }
            ],
        },
    )
    assert assessment.status_code == 200
    assert assessment.json()["status"] == "supported"
