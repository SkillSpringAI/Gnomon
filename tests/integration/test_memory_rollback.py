"""Versioned memory recovery and rollback contracts."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from conftest import purge_test_tasks
from fastapi.testclient import TestClient

from research_agent.api.app import create_app
from research_agent.application.memory_service import MemoryService
from research_agent.domain.memory import MemoryAuthority, MemoryChangeProposal, MemoryDenied
from research_agent.domain.research import ClaimCreate, ClaimSourceLink, SupportType
from research_agent.persistence.database import SessionFactory, engine
from research_agent.persistence.models import (
    MemoryChangeRecord,
)


@pytest.fixture
def memory_task():
    application = create_app()
    with TestClient(application) as client:
        task_response = client.post(
            "/investigations",
            json={
                "title": "Rollback contract",
                "objective": "Test governed recovery.",
                "hypotheses": [{"label": "H1", "statement": "The claim is relevant."}],
            },
        )
        assert task_response.status_code == 201, task_response.text
        task_id = task_response.json()["task"]["id"]
        source_response = client.post(
            f"/investigations/{task_id}/sources",
            json={
                "source_type": "document",
                "title": "Rollback source",
                "uri": "https://example.test/rollback",
                "content": "Observed evidence for rollback.",
            },
        )
        assert source_response.status_code == 201, source_response.text
        source_id = source_response.json()["id"]
        claim_response = client.post(
            f"/investigations/{task_id}/claims",
            json={
                "statement": "Original governed statement.",
                "confidence": 0.4,
                "source_links": [{"source_id": source_id, "support_type": "supporting"}],
            },
        )
        assert claim_response.status_code == 201, claim_response.text
        claim_id = claim_response.json()["id"]
        with SessionFactory() as session:
            change = session.query(MemoryChangeRecord).filter_by(target_id=UUID(claim_id)).one()
            change_id = change.change_id
        try:
            yield client, task_id, claim_id, source_id, change_id
        finally:
            with engine.begin() as connection:
                purge_test_tasks(connection, [UUID(task_id)])


def test_normal_rollback_creates_new_version_and_preserves_history(memory_task):
    client, task_id, claim_id, _, original_id = memory_task
    update = client.post(
        f"/investigations/{task_id}/memory/changes",
        json={
            "target_type": "claim",
            "target_id": claim_id,
            "operation": "UPDATE",
            "expected_version": 1,
            "reason": "correct wording",
            "claim": {
                "statement": "Updated governed statement.",
                "confidence": 0.7,
                "source_links": [{"source_id": memory_task[3], "support_type": "supporting"}],
            },
        },
    )
    assert update.status_code == 200, update.text
    update_id = update.json()["change_id"]
    reversal = client.post(
        f"/investigations/{task_id}/memory/changes/{update_id}/reverse",
        json={"reason": "restore prior wording"},
    )
    assert reversal.status_code == 200, reversal.text
    assert reversal.json()["previous_version"] == 2
    assert reversal.json()["version"] == 3
    assert reversal.json()["reverses_change_id"] == update_id
    history = client.get(f"/investigations/{task_id}/memory/changes/{update_id}")
    assert history.status_code == 200
    assert history.json()["resulting_state"]["data"]["statement"] == "Updated governed statement."
    current = client.get(f"/investigations/{task_id}").json()
    assert current["task"]["id"] == task_id


def test_target_history_and_version_reconstruction(memory_task):
    client, task_id, claim_id, source_id, _ = memory_task

    for operation, version in (("UPDATE", 1), ("ARCHIVE", 2), ("RESTORE", 3)):
        payload = {
            "target_type": "claim",
            "target_id": claim_id,
            "operation": operation,
            "expected_version": version,
            "reason": f"apply {operation.lower()}",
        }
        if operation == "UPDATE":
            payload["claim"] = {
                "statement": "Reconstructed governed statement.",
                "confidence": 0.8,
                "source_links": [{"source_id": source_id, "support_type": "supporting"}],
            }
        response = client.post(f"/investigations/{task_id}/memory/changes", json=payload)
        assert response.status_code == 200, response.text

    history = client.get(f"/investigations/{task_id}/memory/{claim_id}/history")
    assert history.status_code == 200, history.text
    body = history.json()
    assert body["target_type"] == "claim"
    assert body["current_version"] == 4
    assert [item["version"] for item in body["changes"]] == [1, 2, 3, 4]
    assert [item["resulting_state"]["lifecycle"] for item in body["changes"]] == [
        "active",
        "active",
        "archived",
        "active",
    ]

    version = client.get(f"/investigations/{task_id}/memory/{claim_id}/versions/3")
    assert version.status_code == 200, version.text
    assert version.json()["state"]["lifecycle"] == "archived"
    assert version.json()["state"]["data"]["statement"] == "Reconstructed governed statement."


def test_missing_or_unknown_memory_version_is_rejected(memory_task):
    client, task_id, claim_id, _, _ = memory_task
    missing = client.get(f"/investigations/{task_id}/memory/{claim_id}/versions/99")
    assert missing.status_code == 409
    unknown_target = client.get(f"/investigations/{task_id}/memory/{uuid4()}/history")
    assert unknown_target.status_code == 404


def test_duplicate_rollback_is_idempotent(memory_task):
    client, task_id, claim_id, source_id, original_id = memory_task
    payload = {
        "target_type": "claim",
        "target_id": claim_id,
        "operation": "UPDATE",
        "expected_version": 1,
        "reason": "change",
        "claim": {
            "statement": "Changed once.",
            "source_links": [{"source_id": source_id, "support_type": "supporting"}],
        },
    }
    changed = client.post(f"/investigations/{task_id}/memory/changes", json=payload).json()
    reversal = {"change_id": str(uuid4()), "reason": "undo"}
    first = client.post(
        f"/investigations/{task_id}/memory/changes/{changed['change_id']}/reverse", json=reversal
    )
    second = client.post(
        f"/investigations/{task_id}/memory/changes/{changed['change_id']}/reverse",
        json={"reason": "retry"},
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["change_id"] == second.json()["change_id"]


def test_stale_update_and_concurrent_modification_are_rejected(memory_task):
    client, task_id, claim_id, source_id, _ = memory_task
    base = {
        "target_type": "claim",
        "target_id": claim_id,
        "operation": "UPDATE",
        "expected_version": 1,
        "reason": "first",
        "claim": {
            "statement": "First",
            "source_links": [{"source_id": source_id, "support_type": "supporting"}],
        },
    }
    assert client.post(f"/investigations/{task_id}/memory/changes", json=base).status_code == 200
    stale = base | {"reason": "stale", "change_id": str(uuid4())}
    response = client.post(f"/investigations/{task_id}/memory/changes", json=stale)
    assert response.status_code == 409


def test_rollback_conflicts_when_dependent_assessment_exists(memory_task):
    client, task_id, claim_id, source_id, _ = memory_task
    changed = client.post(
        f"/investigations/{task_id}/memory/changes",
        json={
            "target_type": "claim",
            "target_id": claim_id,
            "operation": "UPDATE",
            "expected_version": 1,
            "reason": "change",
            "claim": {
                "statement": "Changed",
                "source_links": [{"source_id": source_id, "support_type": "supporting"}],
            },
        },
    ).json()
    hypothesis_id = client.get(f"/investigations/{task_id}").json()["task"]["brief"]["hypotheses"][
        0
    ]["id"]
    assessment = client.put(
        f"/investigations/{task_id}/hypotheses/{hypothesis_id}/assessment",
        json={
            "status": "supported",
            "summary": "Dependent",
            "evidence_links": [{"claim_id": claim_id, "relation": "supporting"}],
        },
    )
    assert assessment.status_code == 200
    response = client.post(
        f"/investigations/{task_id}/memory/changes/{changed['change_id']}/reverse",
        json={"reason": "undo"},
    )
    assert response.status_code == 409


def test_rollback_conflicts_after_newer_modification(memory_task):
    client, task_id, claim_id, source_id, _ = memory_task
    first = client.post(
        f"/investigations/{task_id}/memory/changes",
        json={
            "target_type": "claim",
            "target_id": claim_id,
            "operation": "UPDATE",
            "expected_version": 1,
            "reason": "first",
            "claim": {
                "statement": "First",
                "source_links": [{"source_id": source_id, "support_type": "supporting"}],
            },
        },
    ).json()
    second = client.post(
        f"/investigations/{task_id}/memory/changes",
        json={
            "target_type": "claim",
            "target_id": claim_id,
            "operation": "UPDATE",
            "expected_version": 2,
            "reason": "second",
            "claim": {
                "statement": "Second",
                "source_links": [{"source_id": source_id, "support_type": "supporting"}],
            },
        },
    )
    assert second.status_code == 200
    response = client.post(
        f"/investigations/{task_id}/memory/changes/{first['change_id']}/reverse",
        json={"reason": "stale undo"},
    )
    assert response.status_code == 409


def test_rollback_after_48_hours_is_rejected(memory_task):
    _, task_id, _, _, change_id = memory_task
    from research_agent.application import memory_service

    with SessionFactory() as session:
        record = session.get(MemoryChangeRecord, change_id)
        record.timestamp = memory_service.utc_now() - timedelta(hours=48, seconds=1)
        session.commit()
    client = memory_task[0]
    response = client.post(
        f"/investigations/{task_id}/memory/changes/{change_id}/reverse", json={"reason": "too late"}
    )
    assert response.status_code == 409


def test_denied_memory_commit_is_audited(memory_task):
    client, task_id, claim_id, source_id, _ = memory_task
    proposal = MemoryChangeProposal(
        target_type="claim",
        target_id=UUID(claim_id),
        operation="UPDATE",
        expected_version=1,
        reason="unauthorized attempt",
        claim=ClaimCreate(
            statement="Attempted mutation",
            source_links=[
                ClaimSourceLink(source_id=UUID(source_id), support_type=SupportType.SUPPORTING)
            ],
        ),
    )
    with SessionFactory() as session:
        with pytest.raises(MemoryDenied):
            MemoryService(session).apply(
                proposal,
                MemoryAuthority("model", UUID(task_id), can_commit=True),
            )
    events = client.get(f"/investigations/{task_id}/events").json()
    security = [event for event in events if event["event_type"] == "security.event"]
    assert security
    assert security[-1]["payload"]["result"] == "rejected"
    assert security[-1]["payload"]["change_reason"] == "unauthorized_memory_mutation"


def test_operator_reasons_remain_in_history_but_not_public_events(memory_task):
    client, task_id, claim_id, source_id, _ = memory_task
    private = "Private source excerpt https://private.test/person secret=example-credential"
    response = client.post(
        f"/investigations/{task_id}/memory/changes",
        json={
            "target_type": "claim",
            "target_id": claim_id,
            "operation": "UPDATE",
            "expected_version": 1,
            "reason": private,
            "claim": {
                "statement": "Revised statement.",
                "confidence": 0.5,
                "source_links": [{"source_id": source_id, "support_type": "supporting"}],
            },
        },
    )
    assert response.status_code == 200, response.text
    change_id = response.json()["change_id"]
    assert (
        client.get(f"/investigations/{task_id}/memory/changes/{change_id}").json()["reason"]
        == private
    )
    reversed_response = client.post(
        f"/investigations/{task_id}/memory/changes/{change_id}/reverse", json={"reason": private}
    )
    assert reversed_response.status_code == 200, reversed_response.text
    assert reversed_response.json()["reason"] == private
    events = client.get(f"/investigations/{task_id}/events")
    assert private not in events.text and "private.test" not in events.text
    memory_events = [event for event in events.json() if event["event_type"].startswith("memory.")]
    assert memory_events[-1]["payload"]["change_reason"] == "operator_memory_reversal"
    assert memory_events[-2]["payload"]["change_reason"] == "operator_memory_change"
    assert memory_events[-2]["payload"]["change_id"] == change_id

    # Characterize a pre-12B stored event and verify projection does not mutate history.
    from research_agent.persistence.models import ResearchEventRecord

    with SessionFactory() as session:
        record = (
            session.query(ResearchEventRecord)
            .filter_by(task_id=UUID(task_id), event_type="memory.reversed")
            .one()
        )
        event_id = record.id
        record.payload = {**record.payload, "change_reason": private}
        session.commit()
    events = client.get(f"/investigations/{task_id}/events")
    assert events.status_code == 200 and private not in events.text
    with SessionFactory() as session:
        assert session.get(ResearchEventRecord, event_id).payload["change_reason"] == private


def test_task_archive_retains_events_and_attributable_memory(memory_task):
    client, task_id, _, _, change_id = memory_task
    before = client.get(f"/investigations/{task_id}/events").json()
    for expected, status in (("active", "abandoned"), ("abandoned", "archived")):
        response = client.patch(
            f"/investigations/{task_id}/status",
            json={
                "expected_status": expected,
                "status": status,
            },
        )
        assert response.status_code == 200, response.text
    after = client.get(f"/investigations/{task_id}/events").json()
    assert {event["id"] for event in before}.issubset({event["id"] for event in after})
    historical = client.get(f"/investigations/{task_id}/memory/changes/{change_id}")
    assert historical.status_code == 200
    assert historical.json()["task_id"] == task_id
