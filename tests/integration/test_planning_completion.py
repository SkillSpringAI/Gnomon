"""Completion follows persisted evidence state rather than objective wording."""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from research_agent.adapters.agents.fake import FakeAgentNetwork, FakeScenario
from research_agent.api.app import create_app
from research_agent.application.agent_evidence_service import AgentEvidenceService
from research_agent.domain.agents import AgentQuestion
from research_agent.persistence.database import SessionFactory, engine
from research_agent.persistence.models import ResearchTaskRecord


@pytest.fixture
def investigation():
    with TestClient(create_app()) as client:
        task = client.post(
            "/investigations",
            json={"title": "Planning completion", "objective": "Review evidence."},
        ).json()["task"]
        try:
            yield client, task
        finally:
            with engine.begin() as connection:
                connection.execute(
                    delete(ResearchTaskRecord).where(ResearchTaskRecord.id == UUID(task["id"]))
                )


def plan(client, task_id):
    response = client.post(f"/investigations/{task_id}/cycles")
    assert response.status_code == 200, response.text
    return response.json()["task"]["cycles"][-1]


def complete(client, task_id, cycle, unresolved=()):
    url = f"/investigations/{task_id}/cycles/{cycle['number']}"
    assert client.post(f"{url}/start").status_code == 200
    response = client.post(f"{url}/outcome", json={
        "status": "completed", "result_summary": "Operator reviewed this evidence.",
        "unresolved_objectives": list(unresolved),
    })
    assert response.status_code == 200, response.text
    return response.json()["task"]["cycles"][cycle["number"] - 1]


def add_observation(task_id, scenario):
    network = FakeAgentNetwork(scenario)
    question = AgentQuestion(
        task_id=UUID(task_id), question="Does premise A hold?",
        agent_id=network.discover(limit=1)[0].id,
    )
    with SessionFactory() as session:
        return AgentEvidenceService(session, network).ask_and_record(question)


def test_new_agent_evidence_reopens_completed_review_but_unrelated_evidence_does_not(investigation):
    client, task = investigation
    task_id = task["id"]
    first = add_observation(task_id, FakeScenario.HONEST)
    second = add_observation(task_id, FakeScenario.CONTRADICTORY)
    review = plan(client, task_id)
    reason = review["planning_basis"][0]
    assert reason["reason"] == "agent_contradiction"
    assert set(reason["source_ids"]) == {str(first.id), str(second.id)}
    assert len(reason["evidence_fingerprint"]) == 64
    completed = complete(client, task_id, review)
    with TestClient(create_app()) as fresh:
        unchanged = plan(fresh, task_id)
        assert "agent_contradiction" not in [b["reason"] for b in unchanged["planning_basis"]]
        assert fresh.post(f"/investigations/{task_id}/sources", json={
            "source_type": "document", "title": "Unrelated", "content": "Other material."
        }).status_code == 201
        unrelated = plan(fresh, task_id)
        assert "agent_contradiction" not in [b["reason"] for b in unrelated["planning_basis"]]
        third = add_observation(task_id, FakeScenario.CONTRADICTORY)
        reopened = plan(fresh, task_id)
        assert reopened["objectives"][0] == review["objectives"][0]
        updated = reopened["planning_basis"][0]
        assert updated["reason"] == "agent_contradiction"
        assert set(updated["source_ids"]) == {str(first.id), str(second.id), str(third.id)}
        assert updated["evidence_fingerprint"] != reason["evidence_fingerprint"]
        history = fresh.get(f"/investigations/{task_id}").json()["task"]["cycles"]
        assert history[review["number"] - 1] == completed


def test_collection_unresolved_work_survives_until_explicit_completion(investigation):
    client, task = investigation
    task_id = task["id"]
    response = client.post(f"/investigations/{task_id}/cycles/1/run", json={"max_agents": 1})
    assert response.status_code == 200
    original = response.json()["task"]["cycles"][0]
    objective = original["objectives"][0]
    assert original["unresolved_objectives"] == [objective]
    next_cycle = plan(client, task_id)
    assert objective in next_cycle["objectives"]
    index = next_cycle["objectives"].index(objective)
    basis = next_cycle["planning_basis"][index]
    complete(client, task_id, next_cycle, unresolved=[objective])
    with TestClient(create_app()) as fresh:
        continued = plan(fresh, task_id)
        assert objective in continued["objectives"]
        assert continued["planning_basis"][continued["objectives"].index(objective)] == basis
        complete(fresh, task_id, continued)
        final = plan(fresh, task_id)
        assert objective not in final["objectives"]
