"""Exercise runner boundaries using real database sessions and controlled adapters."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from research_agent.adapters.agents.fake import FakeAgentNetwork
from research_agent.adapters.llm.rule_based import RuleBasedClaimExtractor
from research_agent.api.app import create_app
from research_agent.application.audit_service import AuditService
from research_agent.domain.events import EventType
from research_agent.persistence.database import SessionFactory, engine
from research_agent.persistence.models import ResearchTaskRecord
from research_agent.persistence.repositories import SqlAlchemyResearchTaskRepository
from research_agent.ports.agent_network import AgentNetworkError


@pytest.fixture
def investigation():
    with TestClient(create_app()) as client:
        task = client.post(
            "/investigations", json={"title": "Runner safety", "objective": "Review evidence."}
        ).json()["task"]
        task_id = UUID(task["id"])
        try:
            yield client, task_id
        finally:
            with engine.begin() as connection:
                connection.execute(
                    delete(ResearchTaskRecord).where(ResearchTaskRecord.id == task_id)
                )


def cycle(client, task_id):
    return client.get(f"/investigations/{task_id}").json()["task"]["cycles"][0]


def test_overlapping_runs_only_one_acquires_investigation(investigation, monkeypatch):
    client, task_id = investigation
    entered, release = Event(), Event()
    original = FakeAgentNetwork.ask
    calls = []

    def waiting_ask(network, question):
        calls.append(question.id)
        entered.set()
        assert release.wait(10), "test did not release adapter"
        return original(network, question)

    # A second planned cycle must not bypass ownership of the first.
    assert client.post(f"/investigations/{task_id}/cycles").status_code == 200
    monkeypatch.setattr(FakeAgentNetwork, "ask", waiting_ask)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            client.post, f"/investigations/{task_id}/cycles/1/run", json={"max_agents": 1}
        )
        try:
            assert entered.wait(10)
            for number in (1, 2):
                rejected = client.post(f"/investigations/{task_id}/cycles/{number}/run", json={})
                assert rejected.status_code == 409, rejected.text
            assert client.post(f"/investigations/{task_id}/cycles/2/start").status_code == 409
        finally:
            release.set()
        assert future.result(timeout=10).status_code == 200
    assert len(calls) == 1
    assert len(cycle(client, task_id)["evidence_ids"]) == 1


@pytest.mark.parametrize("stage", ["acquisition", "extraction"])
def test_pause_during_adapter_work_prevents_next_commit(investigation, monkeypatch, stage):
    client, task_id = investigation
    target = FakeAgentNetwork if stage == "acquisition" else RuleBasedClaimExtractor
    method = "ask" if stage == "acquisition" else "extract"
    original = getattr(target, method)
    calls = []

    def pause_and_return(adapter, value):
        calls.append(value)
        paused = client.patch(
            f"/investigations/{task_id}/status",
            json={"expected_status": "active", "status": "paused"},
        )
        assert paused.status_code == 200
        return original(adapter, value)

    monkeypatch.setattr(target, method, pause_and_return)
    response = client.post(f"/investigations/{task_id}/cycles/1/run", json={})
    assert response.status_code == 200, response.text
    result = cycle(client, task_id)
    assert result["status"] == "blocked"
    assert result["unresolved_objectives"] == result["objectives"]
    assert len(calls) == 1
    snapshot = client.get(f"/investigations/{task_id}/snapshot").json()
    assert len(snapshot["sources"]) == (0 if stage == "acquisition" else 1)
    assert snapshot["claims"] == []
    assert snapshot["task"]["status"] == "paused"


def test_partial_failure_retains_committed_provenance(investigation, monkeypatch):
    client, task_id = investigation
    original = FakeAgentNetwork.ask
    calls = []

    def fail_second(network, question):
        calls.append(question)
        if len(calls) == 2:
            raise AgentNetworkError("private provider failure")
        return original(network, question)

    monkeypatch.setattr(FakeAgentNetwork, "ask", fail_second)
    response = client.post(f"/investigations/{task_id}/cycles/1/run", json={})
    assert response.status_code == 200
    result = cycle(client, task_id)
    assert result["status"] == "blocked"
    snapshot = client.get(f"/investigations/{task_id}/snapshot").json()
    assert result["evidence_ids"] == [source["id"] for source in snapshot["sources"]]
    assert len(result["evidence_ids"]) == 1
    assert set(result["claim_ids"]) == {claim["id"] for claim in snapshot["claims"]}
    assert result["claim_ids"]
    assert "private provider failure" not in response.text
    assert client.post(f"/investigations/{task_id}/cycles").status_code == 200


@pytest.mark.parametrize("stage", ["discovery", "extraction"])
def test_unexpected_failure_is_raised_and_cycle_recovers(investigation, monkeypatch, stage):
    client, task_id = investigation

    def fail(*args, **kwargs):
        raise RuntimeError("sensitive unexpected error")

    target = FakeAgentNetwork if stage == "discovery" else RuleBasedClaimExtractor
    monkeypatch.setattr(target, "discover" if stage == "discovery" else "extract", fail)
    with pytest.raises(RuntimeError, match="sensitive unexpected error"):
        client.post(f"/investigations/{task_id}/cycles/1/run", json={})
    result = cycle(client, task_id)
    assert result["status"] == "failed"
    assert result["unresolved_objectives"] == result["objectives"]
    assert len(result["evidence_ids"]) == (0 if stage == "discovery" else 1)
    assert result["claim_ids"] == []
    assert result["attempted_objectives"] == ([] if stage == "discovery" else result["objectives"])
    assert result["objective_results"] == (
        []
        if stage == "discovery"
        else [{"objective_index": 0, "source_ids": result["evidence_ids"], "claim_ids": []}]
    )
    assert "sensitive" not in result["result_summary"]
    events = client.get(f"/investigations/{task_id}/events").json()
    assert any(item["event_type"] == "cycle.outcome_recorded" for item in events)
    assert client.post(f"/investigations/{task_id}/cycles").status_code == 200


def test_collection_preserves_all_research_objectives(investigation):
    client, task_id = investigation
    objectives = ["Assess the evidence.", "Check alternative explanations.", "Verify sources."]
    with SessionFactory() as session:
        with SqlAlchemyResearchTaskRepository(session).edit(task_id) as task:
            task.cycles[0].objectives = objectives
    response = client.post(f"/investigations/{task_id}/cycles/1/run", json={"max_agents": 1})
    assert response.status_code == 200
    result = cycle(client, task_id)
    assert result["status"] == "completed"
    assert result["unresolved_objectives"] == objectives
    report = client.get(f"/investigations/{task_id}/report").json()
    assert report["unresolved_objectives"] == objectives


def test_manual_outcome_stops_runner_without_being_overwritten(investigation, monkeypatch):
    client, task_id = investigation
    original = FakeAgentNetwork.ask

    def stop_and_return(network, question):
        result = client.post(
            f"/investigations/{task_id}/cycles/1/outcome",
            json={"status": "failed", "result_summary": "Operator stopped this cycle."},
        )
        assert result.status_code == 200
        return original(network, question)

    monkeypatch.setattr(FakeAgentNetwork, "ask", stop_and_return)
    assert client.post(f"/investigations/{task_id}/cycles/1/run", json={}).status_code == 200
    result = cycle(client, task_id)
    assert result["result_summary"] == "Operator stopped this cycle."
    assert client.get(f"/investigations/{task_id}/snapshot").json()["sources"] == []


def test_extraction_write_failure_rolls_back_claims_and_recovers(investigation, monkeypatch):
    client, task_id = investigation
    original = AuditService.stage

    def fail_extraction_commit(service, task_id, event_type, payload):
        if event_type == EventType.EXTRACTION_COMPLETED:
            raise RuntimeError("simulated audit storage failure")
        return original(service, task_id, event_type, payload)

    monkeypatch.setattr(AuditService, "stage", fail_extraction_commit)
    with pytest.raises(RuntimeError, match="simulated audit storage failure"):
        client.post(f"/investigations/{task_id}/cycles/1/run", json={})
    result = cycle(client, task_id)
    assert result["status"] == "failed"
    assert len(result["evidence_ids"]) == 1
    assert result["claim_ids"] == []
    assert client.get(f"/investigations/{task_id}/snapshot").json()["claims"] == []


@pytest.mark.parametrize("scenario", ["empty", "rate_limited"])
def test_unavailable_agents_do_not_complete_cycle(investigation, monkeypatch, scenario):
    client, task_id = investigation
    if scenario == "empty":
        monkeypatch.setattr(FakeAgentNetwork, "discover", lambda *args, **kwargs: [])
    response = client.post(
        f"/investigations/{task_id}/cycles/1/run",
        json={"scenario": "honest" if scenario == "empty" else scenario},
    )
    assert response.status_code == 200
    result = cycle(client, task_id)
    assert result["status"] == "blocked"
    assert result["evidence_ids"] == result["claim_ids"] == []

    assert result["attempted_objectives"] == ([] if scenario == "empty" else result["objectives"])
    assert result["objective_results"] == (
        [] if scenario == "empty" else [{"objective_index": 0, "source_ids": [], "claim_ids": []}]
    )


def test_pause_after_discovery_records_no_attempt(investigation, monkeypatch):
    client, task_id = investigation
    original = FakeAgentNetwork.discover

    def discover(network, **kwargs):
        agents = original(network, **kwargs)
        assert (
            client.patch(
                f"/investigations/{task_id}/status",
                json={"expected_status": "active", "status": "paused"},
            ).status_code
            == 200
        )
        return agents

    monkeypatch.setattr(FakeAgentNetwork, "discover", discover)
    response = client.post(f"/investigations/{task_id}/cycles/1/run", json={})
    assert response.status_code == 200
    result = cycle(client, task_id)
    assert result["status"] == "blocked"
    assert result["attempted_objectives"] == result["objective_results"] == []


def test_multi_objective_agent_result_survives_partial_failure(investigation, monkeypatch):
    client, task_id = investigation
    with SessionFactory() as session:
        with SqlAlchemyResearchTaskRepository(session).edit(task_id) as task:
            task.cycles[0].objectives = ["Review A.", "Review B.", "Review C."]
    original = FakeAgentNetwork.ask
    calls = []

    def ask(network, question):
        calls.append(question)
        if len(calls) == 2:
            raise AgentNetworkError("Unavailable")
        return original(network, question)

    monkeypatch.setattr(FakeAgentNetwork, "ask", ask)
    response = client.post(
        f"/investigations/{task_id}/cycles/1/run", json={"objective_indices": [2, 0]}
    )
    assert response.status_code == 200, response.text
    result = cycle(client, task_id)
    assert result["status"] == "blocked"
    assert result["attempted_objectives"] == ["Review C.", "Review A."]
    assert result["evidence_ids"] and result["claim_ids"]
    assert result["objective_results"] == [
        {
            "objective_index": index,
            "source_ids": result["evidence_ids"],
            "claim_ids": result["claim_ids"],
        }
        for index in [2, 0]
    ]
    report = client.get(f"/investigations/{task_id}/report").json()
    assert report["cycles"][0]["objective_results"] == result["objective_results"]


@pytest.mark.parametrize("failure", ["conflict", "audit_once", "audit_always"])
def test_outcome_write_failure_is_not_reported_as_success(investigation, monkeypatch, failure):
    from research_agent.application.research_service import ResearchService, TaskStateConflict

    client, task_id = investigation
    calls = []
    if failure == "conflict":

        def reject(*args, **kwargs):
            raise TaskStateConflict("Rejected recovery mapping")

        monkeypatch.setattr(ResearchService, "record_cycle_outcome", reject)
        response = client.post(f"/investigations/{task_id}/cycles/1/run", json={})
        assert response.status_code == 409, response.text
    else:
        original = AuditService.stage

        def reject_audit(service, task_id, event_type, payload):
            if event_type == EventType.CYCLE_OUTCOME_RECORDED:
                calls.append(event_type)
                if failure == "audit_always" or len(calls) == 1:
                    raise RuntimeError("Outcome audit unavailable")
            return original(service, task_id, event_type, payload)

        monkeypatch.setattr(AuditService, "stage", reject_audit)
        with pytest.raises(RuntimeError, match="Outcome audit unavailable"):
            client.post(f"/investigations/{task_id}/cycles/1/run", json={})
    result = cycle(client, task_id)
    state = client.get(f"/investigations/{task_id}/snapshot").json()
    assert state["sources"] and state["claims"]
    events = client.get(f"/investigations/{task_id}/events").json()
    outcomes = [item for item in events if item["event_type"] == "cycle.outcome_recorded"]
    if failure == "audit_once":
        assert result["status"] == "failed"
        assert result["objective_results"] == [
            {
                "objective_index": 0,
                "source_ids": result["evidence_ids"],
                "claim_ids": result["claim_ids"],
            }
        ]
        assert len(outcomes) == 1
    else:
        assert result["status"] == "active"
        assert result["objective_results"] == result["evidence_ids"] == []
        assert outcomes == []


@pytest.mark.parametrize("index", [True, "0", 0.0])
def test_agent_objective_index_requires_an_integer(investigation, index):
    client, task_id = investigation
    response = client.post(
        f"/investigations/{task_id}/cycles/1/run", json={"objective_indices": [index]}
    )
    assert response.status_code == 422
    assert cycle(client, task_id)["status"] == "planned"
