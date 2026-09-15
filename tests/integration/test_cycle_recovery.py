"""Recovery after process death, concurrent progress, and late worker returns."""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.orm import Session
from test_agent_cycle_safety import investigation  # noqa: F401
from test_source_cycle import source_cycle  # noqa: F401

from research_agent.adapters.agents.fake import FakeAgentNetwork
from research_agent.application.audit_service import AuditService
from research_agent.application.cycle_progress import CycleProgress
from research_agent.application.evidence_service import EvidenceService
from research_agent.application.research_service import ResearchService
from research_agent.domain.events import EventType
from research_agent.domain.research import SourceCreate, SourceType
from research_agent.persistence.database import SessionFactory
from research_agent.persistence.models import ResearchCycleAttemptRecord, ResearchCycleRecord
from research_agent.persistence.repositories import SqlAlchemyResearchTaskRepository


def state(client, task_id):
    response = client.get(f"/investigations/{task_id}/report")
    assert response.status_code == 200, response.text
    return response.json()


def recover(client, task_id, fingerprint):
    return client.post(
        f"/investigations/{task_id}/cycles/1/recover",
        json={
            "reason": "Operator confirmed an interrupted run.",
            "expected_fingerprint": fingerprint,
        },
    )


@pytest.mark.parametrize("stage", ["source", "claims"])
def test_process_death_retains_progress_and_can_resume(request, stage):
    client, task_id = request.getfixturevalue("investigation")
    code = """
import os, sys
from uuid import UUID
from research_agent.application.agent_cycle_runner import AgentCycleRunner
from research_agent.application.claim_extraction_service import ClaimExtractionService
from research_agent.persistence.database import SessionFactory
original = ClaimExtractionService.extract_for_source
def crash(self, *args, **kwargs):
    if sys.argv[2] == "claims":
        original(self, *args, **kwargs)
    os._exit(23)
ClaimExtractionService.extract_for_source = crash
with SessionFactory() as session:
    AgentCycleRunner(session).run(UUID(sys.argv[1]), 1, max_agents=1)
"""
    child = subprocess.run(
        [sys.executable, "-c", code, str(task_id), stage], capture_output=True, timeout=30
    )
    assert child.returncode == 23, child.stderr.decode(errors="replace")
    before = state(client, task_id)
    cycle = before["cycles"][0]
    assert cycle["status"] == "active" and cycle["progress_tracked"]
    assert len(cycle["evidence_ids"]) == 1
    assert bool(cycle["claim_ids"]) == (stage == "claims")
    assert cycle["objective_results"][0]["source_ids"] == cycle["evidence_ids"]
    token = cycle["recovery_fingerprint"]
    response = recover(client, task_id, token)
    assert response.status_code == 200, response.text
    after = state(client, task_id)
    assert after["task_status"] == "paused"
    assert after["cycles"][0]["status"] == "failed"
    for field in ("evidence_ids", "claim_ids", "objective_results", "attempted_objectives"):
        assert after["cycles"][0][field] == cycle[field]
    assert after["cycles"][0]["unresolved_objectives"] == cycle["objectives"]
    assert recover(client, task_id, token).status_code == 409
    assert client.post(f"/investigations/{task_id}/cycles").status_code == 409
    assert (
        client.patch(
            f"/investigations/{task_id}/status",
            json={"expected_status": "paused", "status": "active"},
        ).status_code
        == 200
    )
    assert client.post(f"/investigations/{task_id}/cycles").status_code == 200
    events = client.get(f"/investigations/{task_id}/events").json()
    assert sum(item["event_type"] == "cycle.recovered" for item in events) == 1
    assert "Operator confirmed" not in str(events)


def test_source_recovery_fences_late_return_even_after_resume(request):
    client, task_id, url, calls, settings = request.getfixturevalue("source_cycle")
    entered, release = Event(), Event()

    def handler(request):
        if len(calls) == 2:
            entered.set()
            assert release.wait(15)
        return httpx.Response(
            200, headers={"content-type": "text/plain"}, text="Retained evidence."
        )

    settings["handler"] = handler
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            client.post,
            f"/investigations/{task_id}/cycles/1/run-sources",
            json={
                "sources": [
                    {"uri": url + "/a", "objective_index": 0},
                    {"uri": url + "/b", "objective_index": 1},
                ]
            },
        )
        try:
            assert entered.wait(10)
            before = state(client, task_id)["cycles"][0]
            assert len(before["evidence_ids"]) == 1 and before["claim_ids"]
            assert recover(client, task_id, before["recovery_fingerprint"]).status_code == 200
            assert (
                client.patch(
                    f"/investigations/{task_id}/status",
                    json={"expected_status": "paused", "status": "active"},
                ).status_code
                == 200
            )
            assert client.post(f"/investigations/{task_id}/cycles").status_code == 200
        finally:
            release.set()
        assert future.result(timeout=10).status_code == 200
    after = state(client, task_id)
    assert len(after["sources"]) == 1
    assert after["cycles"][0]["status"] == "failed"
    assert after["cycles"][0]["objective_results"] == before["objective_results"]


def test_stale_recovery_and_audit_failure_leave_cycle_active(request, monkeypatch):
    client, task_id = request.getfixturevalue("investigation")
    assert client.post(f"/investigations/{task_id}/cycles/1/start").status_code == 200
    old = state(client, task_id)["cycles"][0]
    assert not old["progress_tracked"]
    with SessionFactory() as session:
        CycleProgress(session, task_id, 1).attempt([0])
    assert recover(client, task_id, old["recovery_fingerprint"]).status_code == 409
    original = AuditService.stage

    def fail(service, task_id, event_type, payload):
        if event_type == EventType.CYCLE_RECOVERED:
            raise RuntimeError("Recovery audit unavailable")
        return original(service, task_id, event_type, payload)

    monkeypatch.setattr(AuditService, "stage", fail)
    token = state(client, task_id)["cycles"][0]["recovery_fingerprint"]
    with pytest.raises(RuntimeError, match="Recovery audit unavailable"):
        recover(client, task_id, token)
    current = state(client, task_id)
    assert current["task_status"] == "active" and current["cycles"][0]["status"] == "active"


def test_cycle_activation_rolls_back_if_attempt_creation_fails(request, monkeypatch):
    client, task_id = request.getfixturevalue("investigation")
    original_add = Session.add

    def fail_attempt_add(session, value):
        if isinstance(value, ResearchCycleAttemptRecord):
            raise RuntimeError("attempt creation unavailable")
        original_add(session, value)

    monkeypatch.setattr(Session, "add", fail_attempt_add)
    with SessionFactory() as session:
        with pytest.raises(RuntimeError, match="attempt creation unavailable"):
            ResearchService(SqlAlchemyResearchTaskRepository(session)).start_cycle(
                task_id,
                1,
                track_progress=True,
                attempt_id=uuid4(),
            )
    with SessionFactory() as session:
        cycle = session.query(ResearchCycleRecord).filter_by(task_id=task_id).one()
        attempts = session.query(ResearchCycleAttemptRecord).filter_by(task_id=task_id).all()
        assert cycle.status == "planned"
        assert attempts == []


def test_source_and_progress_commit_or_rollback_together(request, monkeypatch):
    client, task_id = request.getfixturevalue("investigation")
    assert client.post(f"/investigations/{task_id}/cycles/1/start").status_code == 200
    with SessionFactory() as session:
        progress = CycleProgress(session, task_id, 1)
        progress.attempt([0])
        original = AuditService.stage

        def fail(service, task_id, event_type, payload):
            if event_type == EventType.CYCLE_PROGRESS_RECORDED:
                raise RuntimeError("Progress audit unavailable")
            return original(service, task_id, event_type, payload)

        monkeypatch.setattr(AuditService, "stage", fail)
        with pytest.raises(RuntimeError, match="Progress audit unavailable"):
            EvidenceService(session).create_source(
                task_id,
                SourceCreate(
                    source_type=SourceType.DOCUMENT, title="Atomic progress", content="Evidence."
                ),
                after_write=lambda source: progress.source(source, [0]),
            )
    current = state(client, task_id)
    assert current["sources"] == [] and current["cycles"][0]["evidence_ids"] == []


def test_concurrent_recoveries_close_once(request):
    client, task_id = request.getfixturevalue("investigation")
    assert client.post(f"/investigations/{task_id}/cycles/1/start").status_code == 200
    token = state(client, task_id)["cycles"][0]["recovery_fingerprint"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(recover, client, task_id, token) for _ in range(2)]
        assert sorted(item.result().status_code for item in futures) == [200, 409]


def test_agent_recovery_rejects_late_evidence_after_resume(request, monkeypatch):
    client, task_id = request.getfixturevalue("investigation")
    entered, release = Event(), Event()
    original = FakeAgentNetwork.ask

    def wait_for_recovery(network, question):
        entered.set()
        assert release.wait(15)
        return original(network, question)

    monkeypatch.setattr(FakeAgentNetwork, "ask", wait_for_recovery)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(client.post, f"/investigations/{task_id}/cycles/1/run", json={})
        try:
            assert entered.wait(10)
            before = state(client, task_id)["cycles"][0]
            assert before["attempted_objectives"] and before["evidence_ids"] == []
            assert recover(client, task_id, before["recovery_fingerprint"]).status_code == 200
            assert (
                client.patch(
                    f"/investigations/{task_id}/status",
                    json={"expected_status": "paused", "status": "active"},
                ).status_code
                == 200
            )
            assert client.post(f"/investigations/{task_id}/cycles").status_code == 200
        finally:
            release.set()
        assert future.result(timeout=10).status_code == 200
    assert state(client, task_id)["sources"] == []
    assert state(client, task_id)["cycles"][0]["status"] == "failed"
    with SessionFactory() as session:
        attempt = (
            session.query(ResearchCycleAttemptRecord)
            .filter_by(task_id=task_id)
            .order_by(ResearchCycleAttemptRecord.started_at.desc())
            .first()
        )
        assert attempt is not None
        assert attempt.status == "INTERRUPTED"
        assert attempt.stage == "INTERRUPTED"
        assert attempt.recovery_reason


@pytest.mark.parametrize("runner", ["agent", "source"])
@pytest.mark.parametrize("operator_action", ["recover", "outcome"])
def test_operator_closure_between_activation_and_attachment_fences_runner(
    request,
    monkeypatch,
    runner,
    operator_action,
):
    if runner == "source":
        client, task_id, url, calls, settings = request.getfixturevalue("source_cycle")
        endpoint, body = "run-sources", {"sources": [{"uri": url, "objective_index": 0}]}
    else:
        client, task_id = request.getfixturevalue("investigation")
        endpoint, body = "run", {}
    entered, release = Event(), Event()
    original = CycleProgress.attach

    def attach(progress, attempt_id):
        entered.set()
        assert release.wait(10)
        return original(progress, attempt_id)

    monkeypatch.setattr(CycleProgress, "attach", attach)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            client.post, f"/investigations/{task_id}/cycles/1/{endpoint}", json=body
        )
        try:
            assert entered.wait(10)
            before = state(client, task_id)["cycles"][0]
            with SessionFactory() as session:
                attempt = session.query(ResearchCycleAttemptRecord).filter_by(task_id=task_id).one()
                assert attempt.status == "RUNNING"
            if operator_action == "recover":
                assert recover(client, task_id, before["recovery_fingerprint"]).status_code == 200
            else:
                response = client.post(
                    f"/investigations/{task_id}/cycles/1/outcome",
                    json={
                        "status": "failed",
                        "result_summary": "Operator stopped before dispatch.",
                        "unresolved_objectives": before["objectives"],
                    },
                )
                assert response.status_code == 200, response.text
        finally:
            release.set()
        assert future.result(timeout=10).status_code == 409
    current = state(client, task_id)
    assert current["sources"] == []
    assert current["cycles"][0]["status"] == "failed"
    with SessionFactory() as session:
        attempt = session.query(ResearchCycleAttemptRecord).filter_by(task_id=task_id).one()
        assert attempt.status == ("INTERRUPTED" if operator_action == "recover" else "FAILED")
    if runner == "source":
        assert calls == []


@pytest.mark.parametrize("runner", ["agent", "source"])
def test_runner_startup_attempt_failure_preserves_planned_cycle(request, monkeypatch, runner):
    if runner == "source":
        client, task_id, url, calls, settings = request.getfixturevalue("source_cycle")
        endpoint, body = "run-sources", {"sources": [{"uri": url, "objective_index": 0}]}
    else:
        client, task_id = request.getfixturevalue("investigation")
        endpoint, body = "run", {}
    original = Session.add

    def fail(session, value):
        if isinstance(value, ResearchCycleAttemptRecord):
            raise RuntimeError("attempt insert failed")
        original(session, value)

    monkeypatch.setattr(Session, "add", fail)
    with pytest.raises(RuntimeError, match="attempt insert failed"):
        client.post(f"/investigations/{task_id}/cycles/1/{endpoint}", json=body)
    current = state(client, task_id)
    assert current["cycles"][0]["status"] == "planned" and current["sources"] == []
    with SessionFactory() as session:
        assert session.query(ResearchCycleAttemptRecord).filter_by(task_id=task_id).all() == []
