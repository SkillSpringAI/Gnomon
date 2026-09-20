"""Real registry/persistence and bounded HTTP adapter with controlled transport."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID, uuid4

import httpx
import pytest
from conftest import purge_test_tasks
from fastapi.testclient import TestClient
from sqlalchemy import delete

from research_agent.adapters.llm.rule_based import RuleBasedClaimExtractor
from research_agent.adapters.web.http import HttpSourceRetriever
from research_agent.api.app import create_app
from research_agent.api.routes.evidence import get_source_retriever
from research_agent.application import source_cycle_runner as source_cycle_module
from research_agent.application.security_capability import (
    SecurityCapability,
    SecurityCapabilityDenied,
)
from research_agent.application.source_registry import SourceRegistryService
from research_agent.domain.research import ResearchMethod
from research_agent.persistence.database import SessionFactory, engine
from research_agent.persistence.models import TrustedSourceRecord
from research_agent.persistence.repositories import SqlAlchemyResearchTaskRepository


@pytest.fixture
def source_cycle():
    app = create_app()
    calls = []

    def handler(request):
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<title>Evidence</title><p>This is a test source statement.</p>",
        )

    settings = {"handler": handler}

    def transport(request):
        calls.append(str(request.url))
        return settings["handler"](request)

    def retriever():
        with (
            SessionFactory() as session,
            httpx.Client(transport=httpx.MockTransport(transport)) as http,
        ):
            yield HttpSourceRetriever(
                http, url_policy=SourceRegistryService(session).require_enabled
            )

    app.dependency_overrides[get_source_retriever] = retriever
    with TestClient(app) as client:
        domain = f"{uuid4().hex}.example"
        registry = client.post(
            "/source-registry",
            json={
                "domain": domain,
                "display_name": "Test source",
                "verification_method": "Fixture",
            },
        )
        assert registry.status_code == 201
        assert client.post(f"/source-registry/{domain}/enable").status_code == 200
        task = client.post(
            "/investigations",
            json={
                "title": "Source cycle",
                "objective": "Collect attributable evidence.",
            },
        ).json()["task"]
        task_id = UUID(task["id"])
        try:
            with SessionFactory() as session:
                with SqlAlchemyResearchTaskRepository(session).edit(task_id) as saved:
                    saved.cycles[0].objectives = ["Review premise A.", "Check premise B."]
            yield client, task_id, f"https://{domain}", calls, settings
        finally:
            with engine.begin() as connection:
                purge_test_tasks(connection, [task_id])
                connection.execute(
                    delete(TrustedSourceRecord).where(
                        TrustedSourceRecord.id == UUID(registry.json()["id"])
                    )
                )


def run(client, task_id, sources):
    return client.post(f"/investigations/{task_id}/cycles/1/run-sources", json={"sources": sources})


def target(url, index=0):
    return {"uri": url, "objective_index": index}


def snapshot(client, task_id):
    response = client.get(f"/investigations/{task_id}/snapshot")
    assert response.status_code == 200, response.text
    return response.json()


def test_mid_cycle_source_authority_revocation_stops_second_fetch(
    source_cycle, monkeypatch
):
    client, task_id, url, calls, _ = source_cycle
    original = source_cycle_module.require_capability
    retrieval_checks = 0

    def revoke_before_second_fetch(session, capability):
        nonlocal retrieval_checks
        if capability is SecurityCapability.SOURCE_RETRIEVAL:
            retrieval_checks += 1
            # 1 = runner admission, 2 = first point-of-effect check,
            # 3 = second point-of-effect check.
            if retrieval_checks == 3:
                raise SecurityCapabilityDenied("revoked by test policy")
        return original(session, capability)

    monkeypatch.setattr(
        source_cycle_module, "require_capability", revoke_before_second_fetch
    )
    response = run(client, task_id, [target(url + "/a"), target(url + "/b", 1)])
    assert response.status_code == 200, response.text
    cycle = response.json()["task"]["cycles"][0]
    assert cycle["status"] == "blocked"
    assert len(calls) == 1
    assert calls[0].endswith("/a")


def test_two_sources_produce_durable_outcome_and_next_plan(source_cycle):
    client, task_id, url, calls, _ = source_cycle
    response = run(client, task_id, [target(url + "/a"), target(url + "/b", 1)])
    assert response.status_code == 200, response.text
    cycle = response.json()["task"]["cycles"][0]
    assert cycle["status"] == "completed"
    assert cycle["attempted_objectives"] == cycle["unresolved_objectives"] == cycle["objectives"]
    state = snapshot(client, task_id)
    assert len(state["sources"]) == len(calls) == 2
    assert set(cycle["evidence_ids"]) == {item["id"] for item in state["sources"]}
    assert set(cycle["claim_ids"]) == {item["id"] for item in state["claims"]}
    assert all(item["status"] == "unverified" for item in state["claims"])
    assert all(item["source_type"] == "web_page" for item in state["sources"])
    report = client.get(f"/investigations/{task_id}/report").json()
    assert report["cycles"][0]["attempted_objectives"] == cycle["objectives"]
    results = report["cycles"][0]["objective_results"]
    assert results == state["task"]["cycles"][0]["objective_results"]
    for index, suffix in enumerate(["/a", "/b"]):
        source_id = next(item["id"] for item in state["sources"] if item["uri"].endswith(suffix))
        expected_claims = {
            item["id"]
            for item in state["claims"]
            if any(link["source_id"] == source_id for link in item["source_links"])
        }
        assert results[index]["objective_index"] == index
        assert results[index]["source_ids"] == [source_id]
        assert set(results[index]["claim_ids"]) == expected_claims
    assert client.post(f"/investigations/{task_id}/cycles").status_code == 200


@pytest.mark.parametrize("redirect", [False, True])
def test_disabled_domain_rejected_before_contact_and_audited(source_cycle, redirect):
    client, task_id, url, calls, settings = source_cycle
    if redirect:
        settings["handler"] = lambda request: httpx.Response(
            302, headers={"location": "https://unapproved.invalid/secret"}
        )
    response = run(client, task_id, [target(url if redirect else "https://unapproved.invalid")])
    assert response.status_code == 200
    assert response.json()["task"]["cycles"][0]["status"] == "blocked"
    assert len(calls) == (1 if redirect else 0)
    assert snapshot(client, task_id)["sources"] == []
    events = client.get(f"/investigations/{task_id}/events").json()
    assert any(item["payload"].get("reason") == "domain_not_enabled" for item in events)
    assert "unapproved.invalid" not in str(events)


def test_partial_failure_retains_only_attempted_objectives_and_evidence(source_cycle):
    client, task_id, url, calls, settings = source_cycle
    settings["handler"] = lambda request: httpx.Response(
        200 if len(calls) == 1 else 503,
        headers={"content-type": "text/plain"},
        text="A source supports further investigation.",
    )
    response = run(client, task_id, [target(url + "/a", 1), target(url + "/b", 1)])
    cycle = response.json()["task"]["cycles"][0]
    assert cycle["status"] == "blocked"
    assert cycle["attempted_objectives"] == [cycle["objectives"][1]]
    assert cycle["unresolved_objectives"] == cycle["objectives"]
    assert len(cycle["evidence_ids"]) == 1 and cycle["claim_ids"]
    progress = client.get(
        f"/investigations/{task_id}/cycles/1/attempts/latest"
    )
    assert progress.status_code == 200, progress.text
    retained = progress.json()
    assert retained["attempt_status"] == retained["last_durable_stage"] == "BLOCKED"
    assert retained["retained_evidence_ids"] == cycle["evidence_ids"]
    assert retained["retained_claim_ids"] == cycle["claim_ids"]
    assert retained["attempted_objectives"] == cycle["attempted_objectives"]
    assert retained["unresolved_objectives"] == cycle["unresolved_objectives"]
    assert retained["cycle_status"] == "blocked"
    assert retained["cycle_active"] is False


@pytest.mark.parametrize("stage", ["fetch", "extract"])
def test_pause_prevents_subsequent_commit(source_cycle, monkeypatch, stage):
    client, task_id, url, calls, settings = source_cycle
    original = RuleBasedClaimExtractor.extract

    def pause():
        assert (
            client.patch(
                f"/investigations/{task_id}/status",
                json={
                    "expected_status": "active",
                    "status": "paused",
                },
            ).status_code
            == 200
        )

    if stage == "fetch":

        def handler(request):
            pause()
            return httpx.Response(200, headers={"content-type": "text/plain"}, text="A statement.")

        settings["handler"] = handler
    else:

        def extract(extractor, source):
            pause()
            return original(extractor, source)

        monkeypatch.setattr(RuleBasedClaimExtractor, "extract", extract)
    response = run(client, task_id, [target(url), target(url + "/other", 1)])
    assert response.status_code == 200, response.text
    cycle = response.json()["task"]["cycles"][0]
    assert cycle["status"] == "blocked"
    assert cycle["attempted_objectives"] == [cycle["objectives"][0]]
    state = snapshot(client, task_id)
    assert len(state["sources"]) == (0 if stage == "fetch" else 1)
    assert state["claims"] == [] and len(calls) == 1
    assert state["task"]["cycles"][0]["objective_results"] == [
        {
            "objective_index": 0,
            "source_ids": [item["id"] for item in state["sources"]],
            "claim_ids": [],
        }
    ]


@pytest.mark.parametrize("index", [-1, 99, True, "0"])
def test_invalid_selection_does_not_acquire_or_fetch(source_cycle, index):
    client, task_id, url, calls, _ = source_cycle
    assert run(client, task_id, [target(url, index)]).status_code == 422
    assert snapshot(client, task_id)["task"]["cycles"][0]["status"] == "planned"
    assert calls == []


def test_explicit_method_restriction_is_respected(source_cycle):
    client, task_id, url, calls, _ = source_cycle
    with SessionFactory() as session:
        with SqlAlchemyResearchTaskRepository(session).edit(task_id) as task:
            task.brief.methods = [ResearchMethod.AGENT_QUESTIONING]
    assert run(client, task_id, [target(url)]).status_code == 422
    assert calls == []


def test_duplicate_targets_reuse_source_and_claim_ids(source_cycle):
    client, task_id, url, _, _ = source_cycle
    response = run(client, task_id, [target(url), target(url, 1)])
    cycle = response.json()["task"]["cycles"][0]
    assert cycle["status"] == "completed"
    assert len(cycle["evidence_ids"]) == len(cycle["claim_ids"]) == 1
    assert snapshot(client, task_id)["task"]["cycles"][0]["objective_results"] == [
        {
            "objective_index": index,
            "source_ids": cycle["evidence_ids"],
            "claim_ids": cycle["claim_ids"],
        }
        for index in [0, 1]
    ]


def test_overlapping_agent_run_is_rejected(source_cycle):
    client, task_id, url, _, settings = source_cycle
    entered, release = Event(), Event()

    def handler(request):
        entered.set()
        assert release.wait(10)
        return httpx.Response(200, headers={"content-type": "text/plain"}, text="A statement.")

    settings["handler"] = handler
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(run, client, task_id, [target(url)])
        try:
            assert entered.wait(10)
            assert run(client, task_id, [target(url)]).status_code == 409
            assert (
                client.post(f"/investigations/{task_id}/cycles/1/run", json={}).status_code == 409
            )
        finally:
            release.set()
        assert future.result(timeout=10).status_code == 200


def test_unexpected_extraction_failure_recovers_cycle(source_cycle, monkeypatch):
    client, task_id, url, _, _ = source_cycle

    def fail(*args):
        raise RuntimeError("private failure detail")

    monkeypatch.setattr(RuleBasedClaimExtractor, "extract", fail)
    with pytest.raises(RuntimeError, match="private failure detail"):
        run(client, task_id, [target(url)])
    state = snapshot(client, task_id)
    cycle = state["task"]["cycles"][0]
    assert cycle["status"] == "failed" and len(cycle["evidence_ids"]) == 1
    assert state["claims"] == []
    assert "private failure detail" not in cycle["result_summary"]
    assert cycle["objective_results"] == [
        {"objective_index": 0, "source_ids": cycle["evidence_ids"], "claim_ids": []}
    ]


@pytest.mark.parametrize("count", [0, 3])
def test_source_count_is_bounded_before_acquisition(source_cycle, count):
    client, task_id, url, calls, _ = source_cycle
    assert run(client, task_id, [target(url)] * count).status_code == 422
    assert calls == []
    assert snapshot(client, task_id)["task"]["cycles"][0]["status"] == "planned"


def test_missing_cycle_returns_404_without_fetch(source_cycle):
    client, task_id, url, calls, _ = source_cycle
    response = client.post(
        f"/investigations/{task_id}/cycles/99/run-sources",
        json={
            "sources": [target(url)],
        },
    )
    assert response.status_code == 404
    assert calls == []


@pytest.mark.parametrize(
    "invalid", ["index", "duplicate", "unattempted", "source", "claim", "provenance"]
)
def test_invalid_objective_results_leave_cycle_active(source_cycle, invalid):
    client, task_id, url, _, _ = source_cycle
    collected = run(client, task_id, [target(url + "/a"), target(url + "/b", 1)])
    assert collected.status_code == 200
    saved = collected.json()["task"]["cycles"][0]
    planned = client.post(f"/investigations/{task_id}/cycles").json()["task"]["cycles"][-1]
    number = planned["number"]
    assert client.post(f"/investigations/{task_id}/cycles/{number}/start").status_code == 200
    result = dict(saved["objective_results"][0])
    result["objective_index"] = 0
    payload = {
        "status": "completed",
        "result_summary": "Review associations.",
        "attempted_objectives": [planned["objectives"][0]],
        "evidence_ids": saved["evidence_ids"],
        "claim_ids": saved["claim_ids"],
        "objective_results": [result],
    }
    if invalid == "index":
        result["objective_index"] = 99
    elif invalid == "duplicate":
        payload["objective_results"].append(dict(result))
    elif invalid == "unattempted":
        payload["attempted_objectives"] = []
    elif invalid == "source":
        result["source_ids"] = [str(uuid4())]
    elif invalid == "claim":
        result["claim_ids"] = [str(uuid4())]
    else:
        result["source_ids"] = saved["objective_results"][1]["source_ids"]
    response = client.post(f"/investigations/{task_id}/cycles/{number}/outcome", json=payload)
    assert response.status_code == 409, response.text
    current = snapshot(client, task_id)["task"]["cycles"][-1]
    assert current["status"] == "active" and current["objective_results"] == []


@pytest.mark.parametrize("failure", ["conflict", "audit_once", "audit_always"])
def test_source_outcome_failure_preserves_atomicity(source_cycle, monkeypatch, failure):
    from research_agent.application.audit_service import AuditService
    from research_agent.application.research_service import ResearchService, TaskStateConflict
    from research_agent.domain.events import EventType

    client, task_id, url, _, _ = source_cycle
    calls = []
    if failure == "conflict":

        def reject(*args, **kwargs):
            raise TaskStateConflict("Rejected recovery mapping")

        monkeypatch.setattr(ResearchService, "record_cycle_outcome", reject)
        response = run(client, task_id, [target(url)])
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
            run(client, task_id, [target(url)])
    state = snapshot(client, task_id)
    result = state["task"]["cycles"][0]
    assert state["sources"] and state["claims"]
    events = client.get(f"/investigations/{task_id}/events").json()
    outcomes = [item for item in events if item["event_type"] == "cycle.outcome_recorded"]
    if failure == "audit_once":
        assert result["status"] == "failed" and len(outcomes) == 1
        assert result["objective_results"] == [
            {
                "objective_index": 0,
                "source_ids": result["evidence_ids"],
                "claim_ids": result["claim_ids"],
            }
        ]
    else:
        assert result["status"] == "active" and outcomes == []
        assert result["evidence_ids"] and result["claim_ids"]
        assert result["objective_results"] == [
            {
                "objective_index": 0,
                "source_ids": result["evidence_ids"],
                "claim_ids": result["claim_ids"],
            }
        ]


def test_duplicate_objective_text_keeps_index_associations(source_cycle):
    client, task_id, url, _, _ = source_cycle
    with SessionFactory() as session:
        with SqlAlchemyResearchTaskRepository(session).edit(task_id) as task:
            task.cycles[0].objectives = ["Review evidence.", "Review evidence."]
    response = run(client, task_id, [target(url + "/a", 1), target(url + "/b", 0)])
    assert response.status_code == 200, response.text
    state = snapshot(client, task_id)
    result = state["task"]["cycles"][0]
    assert result["attempted_objectives"] == ["Review evidence."]
    assert [item["objective_index"] for item in result["objective_results"]] == [1, 0]
    by_uri = {item["uri"]: item["id"] for item in state["sources"]}
    assert result["objective_results"][0]["source_ids"] == [by_uri[url + "/a"]]
    assert result["objective_results"][1]["source_ids"] == [by_uri[url + "/b"]]


def test_manual_source_outcome_remains_authoritative(source_cycle, monkeypatch):
    client, task_id, url, _, _ = source_cycle
    original = RuleBasedClaimExtractor.extract

    def stop(extractor, source):
        response = client.post(
            f"/investigations/{task_id}/cycles/1/outcome",
            json={
                "status": "failed",
                "result_summary": "Operator retained collected source.",
                "evidence_ids": [str(source.id)],
                "attempted_objectives": ["Review premise A."],
                "objective_results": [{"objective_index": 0, "source_ids": [str(source.id)]}],
            },
        )
        assert response.status_code == 200, response.text
        return original(extractor, source)

    monkeypatch.setattr(RuleBasedClaimExtractor, "extract", stop)
    response = run(client, task_id, [target(url)])
    assert response.status_code == 200, response.text
    state = snapshot(client, task_id)
    result = state["task"]["cycles"][0]
    assert result["result_summary"] == "Operator retained collected source."
    assert result["objective_results"] == [
        {"objective_index": 0, "source_ids": result["evidence_ids"], "claim_ids": []}
    ]
    assert state["claims"] == []
