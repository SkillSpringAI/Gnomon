"""Review decisions preserve evidence/history and control planning at its evidence boundary."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from test_source_cycle import source_cycle  # noqa: F401

from research_agent.application.audit_service import AuditService
from research_agent.application.cycle_planner import plan_cycle_objectives
from research_agent.domain.events import EventType
from research_agent.domain.research import CyclePlanningBasis
from research_agent.persistence.database import SessionFactory
from research_agent.persistence.models import ResearchClaimRecord
from research_agent.persistence.repositories import SqlAlchemyResearchTaskRepository


@pytest.fixture
def review_task(request):
    client, task_id, url, _, _ = request.getfixturevalue("source_cycle")
    response = client.post(
        f"/investigations/{task_id}/cycles/1/run-sources",
        json={"sources": [{"uri": url, "objective_index": 0}]},
    )
    assert response.status_code == 200, response.text
    yield client, task_id


def report(client, task_id):
    response = client.get(f"/investigations/{task_id}/report")
    assert response.status_code == 200, response.text
    return response.json()


def payload(state, index=0, decision="completed"):
    cycle = state["cycles"][-1]
    reviews = [item for item in cycle["objective_reviews"] if item["objective_index"] == index]
    return {
        "decision": decision,
        "rationale": "Operator reviewed the retained evidence.",
        "source_ids": [state["sources"][0]["id"]],
        "claim_ids": [],
        "expected_revision": len(reviews),
        "expected_evidence_fingerprint": state["review_evidence_fingerprint"],
    }


def review(client, task_id, data, number=1, index=0):
    return client.post(
        f"/investigations/{task_id}/cycles/{number}/objectives/{index}/reviews", json=data
    )


def planned_objectives(task_id):
    with SessionFactory() as session:
        snapshot = SqlAlchemyResearchTaskRepository(session).planning_snapshot(task_id)
        return plan_cycle_objectives(snapshot)[0]


def test_review_suppresses_work_without_rewriting_collection_or_claims(review_task):
    client, task_id = review_task
    before = report(client, task_id)
    assert review(client, task_id, payload(before)).status_code == 200
    after = report(client, task_id)
    assert (
        after["cycles"][0]["unresolved_objectives"] == before["cycles"][0]["unresolved_objectives"]
    )
    assert after["claims"] == before["claims"]
    assert "Review premise A." not in after["unresolved_objectives"]
    assert "Review premise A." not in planned_objectives(task_id)
    assert after["cycles"][0]["objective_reviews"][0]["actor"] == "local_operator"
    events = client.get(f"/investigations/{task_id}/events").json()
    audit = [item for item in events if item["event_type"] == "cycle.objective_reviewed"]
    assert len(audit) == 1 and "Operator reviewed" not in str(audit)


def test_revision_replay_and_correction_preserve_history(review_task):
    client, task_id = review_task
    data = payload(report(client, task_id))
    assert review(client, task_id, data).status_code == 200
    assert review(client, task_id, data).status_code == 409
    state = report(client, task_id)
    first = state["cycles"][0]["objective_reviews"][0]
    assert review(client, task_id, payload(state, decision="unresolved")).status_code == 200
    state = report(client, task_id)
    assert state["cycles"][0]["objective_reviews"][0] == first
    assert [item["revision"] for item in state["cycles"][0]["objective_reviews"]] == [1, 2]
    assert "Review premise A." in planned_objectives(task_id)


def test_changed_evidence_rejects_stale_submission_and_reopens_review(review_task):
    client, task_id = review_task
    before = report(client, task_id)
    assert review(client, task_id, payload(before)).status_code == 200
    stale = payload(report(client, task_id), index=1)
    with SessionFactory() as session:
        claim = session.get(ResearchClaimRecord, before["claims"][0]["id"])
        claim.version += 1
        session.commit()
    assert review(client, task_id, stale, index=1).status_code == 409
    assert "Review premise A." in planned_objectives(task_id)
    assert report(client, task_id)["cycles"][0]["stale_review_ids"]


@pytest.mark.parametrize("invalid", ["sources", "claims", "empty", "blank", "actor"])
def test_invalid_reviews_do_not_write_history(review_task, invalid):
    client, task_id = review_task
    data = payload(report(client, task_id))
    if invalid in {"sources", "claims"}:
        data["source_ids" if invalid == "sources" else "claim_ids"] = [str(uuid4())]
    elif invalid == "empty":
        data["source_ids"] = []
    elif invalid == "blank":
        data["rationale"] = "  "
    else:
        data["actor"] = "model"
    assert review(client, task_id, data).status_code == 422
    assert report(client, task_id)["cycles"][0]["objective_reviews"] == []


def test_review_and_audit_rollback_together(review_task, monkeypatch):
    client, task_id = review_task
    original = AuditService.stage

    def fail(service, task_id, event_type, event_payload):
        if event_type == EventType.OBJECTIVE_REVIEWED:
            raise RuntimeError("Review audit unavailable")
        return original(service, task_id, event_type, event_payload)

    monkeypatch.setattr(AuditService, "stage", fail)
    with pytest.raises(RuntimeError, match="Review audit unavailable"):
        review(client, task_id, payload(report(client, task_id)))
    assert report(client, task_id)["cycles"][0]["objective_reviews"] == []


def test_concurrent_reviews_only_one_revision_wins(review_task):
    client, task_id = review_task
    data = payload(report(client, task_id))
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(review, client, task_id, data) for _ in range(2)]
        assert sorted(item.result().status_code for item in futures) == [200, 409]


def test_review_cannot_change_already_planned_work(review_task):
    client, task_id = review_task
    data = payload(report(client, task_id))
    assert client.post(f"/investigations/{task_id}/cycles").status_code == 200
    assert review(client, task_id, data).status_code == 409


def test_review_history_cannot_be_rewritten(review_task):
    client, task_id = review_task
    assert review(client, task_id, payload(report(client, task_id))).status_code == 200
    with SessionFactory() as session:
        with pytest.raises(ValueError, match="history cannot be rewritten"):
            with SqlAlchemyResearchTaskRepository(session).edit(task_id) as task:
                task.cycles[0].objective_reviews.clear()
    assert len(report(client, task_id)["cycles"][0]["objective_reviews"]) == 1


def test_narrow_review_ignores_unrelated_evidence_but_reopens_for_referenced_change(review_task):
    client, task_id = review_task
    planned = client.post(f"/investigations/{task_id}/cycles").json()["task"]["cycles"][-1]
    index = next(
        i
        for i, basis in enumerate(planned["planning_basis"])
        if basis["reason"] == "unverified_claim"
    )
    assert client.post(f"/investigations/{task_id}/cycles/2/start").status_code == 200
    assert (
        client.post(
            f"/investigations/{task_id}/cycles/2/outcome",
            json={
                "status": "completed",
                "result_summary": "Review pending.",
                "unresolved_objectives": planned["objectives"],
            },
        ).status_code
        == 200
    )
    assert (
        review(
            client, task_id, payload(report(client, task_id), index), number=2, index=index
        ).status_code
        == 200
    )
    objective = planned["objectives"][index]
    assert objective not in planned_objectives(task_id)
    assert (
        client.post(
            f"/investigations/{task_id}/sources",
            json={"source_type": "document", "title": "Unrelated", "content": "Different source."},
        ).status_code
        == 201
    )
    assert objective not in planned_objectives(task_id)
    with SessionFactory() as session:
        claim = session.get(ResearchClaimRecord, planned["planning_basis"][index]["claim_ids"][0])
        claim.version += 1
        session.commit()
    assert objective in planned_objectives(task_id)


def test_duplicate_objectives_need_separate_reviews(review_task):
    client, task_id = review_task
    with SessionFactory() as session:
        with SqlAlchemyResearchTaskRepository(session).edit(task_id) as task:
            task.cycles[0].objectives = ["Review premise A.", "Review premise A."]
            task.cycles[0].unresolved_objectives = ["Review premise A."]
    assert review(client, task_id, payload(report(client, task_id))).status_code == 200
    assert "Review premise A." in planned_objectives(task_id)
    assert review(client, task_id, payload(report(client, task_id), 1), index=1).status_code == 200
    assert "Review premise A." not in planned_objectives(task_id)


def test_reviewed_stopping_criteria_does_not_create_identical_cycle(review_task):
    client, task_id = review_task
    objective = "Review the stopping criteria and decide whether more evidence is needed."
    with SessionFactory() as session:
        repository = SqlAlchemyResearchTaskRepository(session)
        with repository.edit(task_id) as task:
            task.cycles[0].objectives = [objective]
            task.cycles[0].planning_basis = [CyclePlanningBasis(reason="review_stopping_criteria")]
            task.cycles[0].unresolved_objectives = [objective]
        claim_id = report(client, task_id)["claims"][0]["id"]
        claim = session.get(ResearchClaimRecord, claim_id)
        claim.status = "supported"
        session.commit()
    assert review(client, task_id, payload(report(client, task_id))).status_code == 200
    response = client.post(f"/investigations/{task_id}/cycles")
    assert response.status_code == 409
    state = report(client, task_id)
    assert len(state["cycles"]) == 1 and state["task_status"] == "active"


def test_unresolved_review_reopens_legacy_completed_objective(review_task):
    client, task_id = review_task
    with SessionFactory() as session:
        with SqlAlchemyResearchTaskRepository(session).edit(task_id) as task:
            task.cycles[0].unresolved_objectives = []
    assert (
        review(client, task_id, payload(report(client, task_id), decision="unresolved")).status_code
        == 200
    )
    assert "Review premise A." in report(client, task_id)["unresolved_objectives"]
    assert "Review premise A." in planned_objectives(task_id)
