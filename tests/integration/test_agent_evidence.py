"""Agent observations cross the same evidence and audit boundary as other sources."""

from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import delete

from research_agent.adapters.agents.fake import FakeAgentNetwork, FakeScenario
from research_agent.api.app import create_app
from research_agent.application.agent_evidence_service import AgentEvidenceService
from research_agent.domain.agents import AgentQuestion
from research_agent.persistence.database import SessionFactory, engine
from research_agent.persistence.models import ResearchTaskRecord


def test_prompt_injection_observation_is_persisted_as_inert_agent_evidence() -> None:
    with TestClient(create_app()) as client:
        task = client.post(
            "/investigations",
            json={"title": "Agent evidence", "objective": "Test agent boundaries."},
        ).json()["task"]
        task_id = UUID(task["id"])
        network = FakeAgentNetwork(FakeScenario.PROMPT_INJECTION)
        agent = network.discover(limit=1)[0]
        question = AgentQuestion(
            task_id=task_id,
            agent_id=agent.id,
            question="What should be checked next?",
        )
        try:
            with SessionFactory() as session:
                source = AgentEvidenceService(session, network).ask_and_record(question)

            assert source.source_type.value == "agent_message"
            assert "SYSTEM:" in source.content
            assert source.uri is not None and source.uri.startswith("agent://fake/")
            events = client.get(f"/investigations/{task_id}/events").json()
            observation_event = next(
                item for item in events if item["event_type"] == "agent.observation_recorded"
            )
            assert observation_event["payload"]["actor"] == "agent_network"
            assert len(observation_event["payload"]["provenance"]) == 2
            assert client.get(f"/investigations/{task_id}/snapshot").json()["claims"] == []
            report = client.get(f"/investigations/{task_id}/report").json()
            assert report["agent_comparison"]["observation_ids"] == [str(source.id)]
            assert report["agent_comparison"]["independent_agent_count"] == 1
        finally:
            with engine.begin() as connection:
                connection.execute(
                    delete(ResearchTaskRecord).where(ResearchTaskRecord.id == task_id)
                )


def test_local_agent_cycle_runs_evidence_claims_report_and_next_plan() -> None:
    with TestClient(create_app()) as client:
        task = client.post(
            "/investigations",
            json={
                "title": "Agent cycle",
                "objective": "Test the local research loop.",
                "questions": [{"question": "What should be verified?"}],
            },
        ).json()["task"]
        task_id = UUID(task["id"])
        try:
            response = client.post(
                f"/investigations/{task_id}/cycles/1/run",
                json={"scenario": "honest", "max_agents": 2},
            )
            assert response.status_code == 200, response.text
            completed = response.json()["task"]["cycles"][0]
            assert completed["status"] == "completed"
            assert len(completed["evidence_ids"]) == 2
            assert completed["claim_ids"]

            report = client.get(f"/investigations/{task_id}/report").json()
            assert len(report["sources"]) == 2
            assert report["agent_comparison"]["independent_agent_count"] == 2
            next_cycle = client.post(f"/investigations/{task_id}/cycles")
            assert next_cycle.status_code == 200, next_cycle.text
        finally:
            with engine.begin() as connection:
                connection.execute(
                    delete(ResearchTaskRecord).where(ResearchTaskRecord.id == task_id)
                )
