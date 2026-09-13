"""Real registry/persistence and bounded HTTP adapter with controlled transport."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from research_agent.adapters.llm.rule_based import RuleBasedClaimExtractor
from research_agent.adapters.web.http import HttpSourceRetriever
from research_agent.api.app import create_app
from research_agent.api.routes.evidence import get_source_retriever
from research_agent.application.source_registry import SourceRegistryService
from research_agent.domain.research import ResearchMethod
from research_agent.persistence.database import SessionFactory, engine
from research_agent.persistence.models import ResearchTaskRecord, TrustedSourceRecord
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
                connection.execute(
                    delete(ResearchTaskRecord).where(ResearchTaskRecord.id == task_id)
                )
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


@pytest.mark.parametrize("count", [0, 3])
def test_source_count_is_bounded_before_acquisition(source_cycle, count):
    client, task_id, url, calls, _ = source_cycle
    assert run(client, task_id, [target(url)] * count).status_code == 422
    assert calls == []
    assert snapshot(client, task_id)["task"]["cycles"][0]["status"] == "planned"


def test_missing_cycle_returns_404_without_fetch(source_cycle):
    client, task_id, url, calls, _ = source_cycle
    response = client.post(f"/investigations/{task_id}/cycles/99/run-sources", json={
        "sources": [target(url)],
    })
    assert response.status_code == 404
    assert calls == []
