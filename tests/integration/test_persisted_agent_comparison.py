"""Comparison provenance and scope survive ingestion and fresh-session reads."""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from research_agent.adapters.agents.fake import FakeAgentNetwork, FakeScenario
from research_agent.api.app import create_app
from research_agent.application.agent_evidence_service import AgentEvidenceService
from research_agent.domain.agents import AgentQuestion
from research_agent.persistence.database import SessionFactory, engine
from research_agent.persistence.models import ResearchSourceRecord, ResearchTaskRecord


@pytest.fixture
def investigation():
    with TestClient(create_app()) as client:
        task_id = UUID(client.post(
            "/investigations", json={"title": "Comparisons", "objective": "Compare evidence."}
        ).json()["task"]["id"])
        try:
            yield client, task_id
        finally:
            with engine.begin() as connection:
                connection.execute(
                    delete(ResearchTaskRecord).where(ResearchTaskRecord.id == task_id)
                )


def ingest(task_id, network, question_text="Does the evidence support premise A?", agent=0):
    question = AgentQuestion(
        task_id=task_id, question=question_text, agent_id=network.discover(limit=2)[agent].id,
    )
    with SessionFactory() as session:
        source = AgentEvidenceService(session, network).ask_and_record(question)
    return source


@pytest.mark.parametrize("legacy", [False, True])
def test_duplicate_ids_resolve_to_sources_after_reload(investigation, legacy):
    client, task_id = investigation
    network = FakeAgentNetwork(FakeScenario.DUPLICATE)
    first = ingest(task_id, network)
    second = ingest(task_id, network, agent=1)
    assert UUID(first.source_metadata["observation_id"]) != first.id
    assert second.source_metadata["duplicate_of"] == first.source_metadata["observation_id"]
    if legacy:
        with SessionFactory() as session:
            for source in (first, second):
                record = session.get(ResearchSourceRecord, source.id)
                record.source_metadata = {
                    key: value for key, value in record.source_metadata.items()
                    if key not in {"observation_id", "subject_id"}
                }
            session.commit()
    report = client.get(f"/investigations/{task_id}/report").json()
    comparison = report["agent_comparison"]
    assert comparison["comparisons"] == [{
        "left_id": str(first.id), "right_id": str(second.id), "relation": "duplicate",
    }]
    assert set(comparison["observation_ids"]) == {source["id"] for source in report["sources"]}
    assert comparison["distinct_agent_count"] == 2
    assert "independent_agent_count" not in comparison
    assert "do not establish independent evidence" in comparison["note"]
    plan = client.post(f"/investigations/{task_id}/cycles").json()["task"]["cycles"][-1]
    assert all(basis["reason"] != "agent_contradiction" for basis in plan["planning_basis"])


@pytest.mark.parametrize("scope", ["same", "different", "legacy"])
def test_contradiction_subject_controls_report_and_planning(investigation, scope):
    client, task_id = investigation
    first = ingest(task_id, FakeAgentNetwork())
    second = ingest(
        task_id, FakeAgentNetwork(FakeScenario.CONTRADICTORY),
        question_text=("Does premise B hold?" if scope == "different"
                       else "Does the evidence support premise A?"),
        agent=1,
    )
    assert first.source_metadata["question_id"] != second.source_metadata["question_id"]
    if scope == "legacy":
        with SessionFactory() as session:
            record = session.get(ResearchSourceRecord, first.id)
            record.source_metadata = {
                key: value for key, value in record.source_metadata.items() if key != "subject_id"
            }
            session.commit()
    report = client.get(f"/investigations/{task_id}/report").json()
    relation = report["agent_comparison"]["comparisons"][0]["relation"]
    assert relation == ("contradiction" if scope == "same" else "unrelated")
    response = client.post(f"/investigations/{task_id}/cycles")
    assert response.status_code == 200, response.text
    basis = response.json()["task"]["cycles"][-1]["planning_basis"]
    contradictions = [item for item in basis if item["reason"] == "agent_contradiction"]
    assert bool(contradictions) == (scope == "same")
    if contradictions:
        assert set(contradictions[0]["source_ids"]) == {str(first.id), str(second.id)}


def test_more_than_100_observations_keep_report_and_planner_available(investigation):
    client, task_id = investigation
    network = FakeAgentNetwork()
    sources = [ingest(task_id, network, question_text=f"Question {index}?") for index in range(101)]
    response = client.get(f"/investigations/{task_id}/report")
    assert response.status_code == 200, response.text
    report = response.json()
    comparison = report["agent_comparison"]
    assert len(report["sources"]) == 101
    assert len(comparison["observation_ids"]) == 100
    assert comparison["omitted_observation_count"] == 1
    assert str(sources[0].id) not in comparison["observation_ids"]
    assert any("omit 1 older" in item for item in report["limitations"])
    response = client.post(f"/investigations/{task_id}/cycles")
    assert response.status_code == 200, response.text
    basis = response.json()["task"]["cycles"][-1]["planning_basis"]
    assert any(item["reason"] == "agent_comparison_limit" for item in basis)
    assert all(len(item["source_ids"]) <= 100 for item in basis)
