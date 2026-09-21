"""Contract-negative coverage for task-scoped source dependence."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from conftest import purge_test_tasks
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from research_agent.api.app import create_app
from research_agent.application import source_dependence_service as dependence_module
from research_agent.application.audit_service import AuditService
from research_agent.application.security_capability import SecurityCapabilityDenied
from research_agent.application.source_dependence_service import (
    SourceDependenceConflict,
    SourceDependenceService,
)
from research_agent.domain.research import (
    SourceDependenceKind,
    SourceRelationshipCreate,
    SourceRelationshipMutation,
    SourceRelationshipReversal,
)
from research_agent.persistence.database import SessionFactory, engine
from research_agent.persistence.models import (
    ResearchSourceRecord,
    SourceRelationshipChangeRecord,
    SourceRelationshipRecord,
)


@pytest.fixture
def dependence_context():
    with TestClient(create_app()) as client:
        response = client.post(
            "/investigations",
            json={"title": "Dependence contract", "objective": "Test declared dependence."},
        )
        assert response.status_code == 201, response.text
        task_id = UUID(response.json()["task"]["id"])
        source_ids = [uuid4() for _ in range(4)]
        with SessionFactory() as session:
            now = datetime.now(UTC)
            session.add_all(
                ResearchSourceRecord(
                    id=source_id,
                    task_id=task_id,
                    source_type="web_page",
                    title=f"Source {index}",
                    uri=f"https://example.test/{index}",
                    publisher="fixture",
                    content=f"content {index}",
                    content_hash=f"{index:064x}",
                    reliability_score=0.5,
                    observed_at=now,
                    source_metadata={},
                )
                for index, source_id in enumerate(source_ids)
            )
            session.commit()
        try:
            yield task_id, source_ids
        finally:
            with engine.begin() as connection:
                connection.execute(
                    delete(SourceRelationshipChangeRecord).where(
                        SourceRelationshipChangeRecord.task_id == task_id
                    )
                )
                connection.execute(
                    delete(SourceRelationshipRecord).where(
                        SourceRelationshipRecord.task_id == task_id
                    )
                )
                purge_test_tasks(connection, [task_id])


def test_relationship_contract_rejects_self_cross_task_and_cycles(dependence_context):
    task_id, source_ids = dependence_context
    first, second, third = source_ids[:3]
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        with pytest.raises(SourceDependenceConflict, match="cannot reference itself"):
            service.create(
                task_id,
                SourceRelationshipCreate(
                    derived_source_id=first,
                    upstream_source_id=first,
                    kind=SourceDependenceKind.DERIVED_FROM,
                    reason="invalid self link",
                ),
            )
        relationship = service.create(
            task_id,
            SourceRelationshipCreate(
                derived_source_id=first,
                upstream_source_id=second,
                kind=SourceDependenceKind.DERIVED_FROM,
                reason="first edge",
            ),
        )
        with pytest.raises(SourceDependenceConflict, match="would create a cycle"):
            service.create(
                task_id,
                SourceRelationshipCreate(
                    derived_source_id=second,
                    upstream_source_id=first,
                    kind=SourceDependenceKind.DERIVED_FROM,
                    reason="reciprocal edge",
                ),
            )
        service.create(
            task_id,
            SourceRelationshipCreate(
                derived_source_id=second,
                upstream_source_id=third,
                kind=SourceDependenceKind.DERIVED_FROM,
                reason="second edge",
            ),
        )
        with pytest.raises(SourceDependenceConflict, match="would create a cycle"):
            service.create(
                task_id,
                SourceRelationshipCreate(
                    derived_source_id=third,
                    upstream_source_id=first,
                    kind=SourceDependenceKind.DERIVED_FROM,
                    reason="closing edge",
                ),
            )
        assert relationship.revision == 1


def test_operation_retry_is_exact_and_history_is_immutable(dependence_context):
    task_id, source_ids = dependence_context
    first, second, third = source_ids[:3]
    operation_id = uuid4()
    request = SourceRelationshipCreate(
        derived_source_id=first,
        upstream_source_id=second,
        kind=SourceDependenceKind.DERIVED_FROM,
        reason="retryable assertion",
        operation_id=operation_id,
    )
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        accepted = service.create(task_id, request)
        retried = service.create(task_id, request)
        assert retried.relationship_id == accepted.relationship_id
        assert len(service.history(task_id, accepted.relationship_id)) == 1
        with pytest.raises(SourceDependenceConflict, match="different content"):
            service.create(
                task_id,
                request.model_copy(update={"upstream_source_id": third}),
            )


def test_common_origin_is_pairwise_and_projection_preserves_unknown(dependence_context):
    task_id, source_ids = dependence_context
    first, second, third = source_ids[:3]
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        service.create(
            task_id,
            SourceRelationshipCreate(
                source_a_id=first,
                source_b_id=second,
                kind=SourceDependenceKind.COMMON_ORIGIN,
                reason="shared origin",
            ),
        )
        service.create(
            task_id,
            SourceRelationshipCreate(
                source_a_id=second,
                source_b_id=third,
                kind=SourceDependenceKind.COMMON_ORIGIN,
                reason="another shared origin",
            ),
        )
        projection = service.project(task_id, [first])
        assert projection.complete is True
        assert projection.unknown_dependence is True
        assert third in projection.visited_source_ids
        assert len(projection.examined_relationships) == 2


def test_retract_is_versioned_and_reversal_restores_prior_state(dependence_context):
    task_id, source_ids = dependence_context
    first, second = source_ids[:2]
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        accepted = service.create(
            task_id,
            SourceRelationshipCreate(
                derived_source_id=first,
                upstream_source_id=second,
                kind=SourceDependenceKind.DERIVED_FROM,
                reason="temporary assertion",
            ),
        )
        retracted = service.mutate(
            task_id,
            SourceRelationshipMutation(
                relationship_id=accepted.relationship_id,
                expected_revision=1,
                operation="RETRACT",
                reason="withdrawn",
            ),
        )
        assert retracted.lifecycle.value == "retracted"
        restored = service.reverse(
            task_id,
            SourceRelationshipReversal(
                relationship_id=accepted.relationship_id,
                change_id=retracted.latest_change_id,
                expected_revision=2,
                reason="correction",
            ),
        )
        assert restored.lifecycle.value == "active"
        assert [item.operation for item in service.history(task_id, accepted.relationship_id)] == [
            "CREATE",
            "RETRACT",
            "REVERSE",
        ]


def test_missing_or_cross_task_endpoint_is_rejected(dependence_context):
    task_id, source_ids = dependence_context
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        with pytest.raises(SourceDependenceConflict, match="belong to the task"):
            service.create(
                task_id,
                SourceRelationshipCreate(
                    derived_source_id=source_ids[0],
                    upstream_source_id=uuid4(),
                    kind=SourceDependenceKind.DERIVED_FROM,
                    reason="missing endpoint",
                ),
            )


def test_stale_mutation_does_not_change_accepted_state(dependence_context):
    task_id, source_ids = dependence_context
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        accepted = service.create(
            task_id,
            SourceRelationshipCreate(
                derived_source_id=source_ids[0],
                upstream_source_id=source_ids[1],
                kind=SourceDependenceKind.DERIVED_FROM,
                reason="stale revision fixture",
            ),
        )
        service.mutate(
            task_id,
            SourceRelationshipMutation(
                relationship_id=accepted.relationship_id,
                expected_revision=1,
                operation="RETRACT",
                reason="first correction",
            ),
        )
        with pytest.raises(SourceDependenceConflict, match="revision is stale"):
            service.mutate(
                task_id,
                SourceRelationshipMutation(
                    relationship_id=accepted.relationship_id,
                    expected_revision=1,
                    operation="SET",
                    lifecycle="active",
                    direction=accepted.direction,
                    reason="stale correction",
                ),
            )
        assert service.get(task_id, accepted.relationship_id).lifecycle.value == "retracted"


def test_projection_reports_depth_overflow_as_unknown(dependence_context):
    task_id, source_ids = dependence_context
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        for index in range(3):
            service.create(
                task_id,
                SourceRelationshipCreate(
                    derived_source_id=source_ids[index],
                    upstream_source_id=source_ids[index + 1],
                    kind=SourceDependenceKind.DERIVED_FROM,
                    reason=f"bounded edge {index}",
                ),
            )
        service.LIMITS = service.LIMITS.model_copy(update={"max_hops": 1})
        projection = service.project(task_id, [source_ids[0]])
        assert projection.truncated is True
        assert projection.overflow_reason == "depth_limit"
        assert projection.unknown_dependence is True


def test_http_adapters_are_task_scoped_and_preserve_history(dependence_context):
    task_id, source_ids = dependence_context
    first, second = source_ids[:2]
    with TestClient(create_app()) as client:
        payload = {
            "derived_source_id": str(first),
            "upstream_source_id": str(second),
            "kind": "derived_from",
            "reason": "HTTP contract assertion",
        }
        created = client.post(
            f"/investigations/{task_id}/source-dependence/relationships",
            json=payload,
        )
        assert created.status_code == 201, created.text
        relationship_id = created.json()["relationship_id"]
        fetched = client.get(
            f"/investigations/{task_id}/source-dependence/relationships/{relationship_id}"
        )
        assert fetched.status_code == 200
        assert fetched.json()["task_id"] == str(task_id)
        history = client.get(
            f"/investigations/{task_id}/source-dependence/relationships/{relationship_id}/history"
        )
        assert history.status_code == 200
        assert [item["operation"] for item in history.json()] == ["CREATE"]
        projection = client.post(
            f"/investigations/{task_id}/source-dependence/projection",
            json={"root_source_ids": [str(first)]},
        )
        assert projection.status_code == 200
        assert projection.json()["unknown_dependence"] is True
        report = client.get(f"/investigations/{task_id}/report")
        assert report.status_code == 200, report.text
        assert report.json()["source_dependence"]["examined_relationships"]
        assert any("independent evidence" in item for item in report.json()["limitations"])
        planned = client.post(f"/investigations/{task_id}/cycles")
        assert planned.status_code == 200, planned.text
        assert "source_dependence_unknown" in {
            item["reason"] for item in planned.json()["task"]["cycles"][-1]["planning_basis"]
        }


def test_capability_denial_is_exposed_without_writing(dependence_context, monkeypatch):
    task_id, source_ids = dependence_context

    def deny(*_args, **_kwargs):
        raise SecurityCapabilityDenied("denied by contract test")

    monkeypatch.setattr(dependence_module, "require_locked_capability", deny)
    with TestClient(create_app()) as client:
        response = client.post(
            f"/investigations/{task_id}/source-dependence/relationships",
            json={
                "derived_source_id": str(source_ids[0]),
                "upstream_source_id": str(source_ids[1]),
                "kind": "derived_from",
                "reason": "must be denied",
            },
        )
    assert response.status_code == 403
    with SessionFactory() as session:
        assert session.scalar(
            select(SourceRelationshipRecord).where(SourceRelationshipRecord.task_id == task_id)
        ) is None


def test_audit_failure_rolls_back_projection_and_history(dependence_context, monkeypatch):
    task_id, source_ids = dependence_context

    def fail(*_args, **_kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(AuditService, "stage", fail)
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        with pytest.raises(RuntimeError, match="audit unavailable"):
            service.create(
                task_id,
                SourceRelationshipCreate(
                    derived_source_id=source_ids[0],
                    upstream_source_id=source_ids[1],
                    kind=SourceDependenceKind.DERIVED_FROM,
                    reason="must roll back",
                ),
            )
        assert session.scalar(
            select(SourceRelationshipRecord).where(SourceRelationshipRecord.task_id == task_id)
        ) is None
        assert session.scalar(
            select(SourceRelationshipChangeRecord).where(
                SourceRelationshipChangeRecord.task_id == task_id
            )
        ) is None


def test_reversal_expiry_is_rejected(dependence_context):
    task_id, source_ids = dependence_context
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        accepted = service.create(
            task_id,
            SourceRelationshipCreate(
                derived_source_id=source_ids[0],
                upstream_source_id=source_ids[1],
                kind=SourceDependenceKind.DERIVED_FROM,
                reason="expired reversal fixture",
            ),
        )
        change = session.scalar(
            select(SourceRelationshipChangeRecord).where(
                SourceRelationshipChangeRecord.relationship_id == accepted.relationship_id
            )
        )
        assert change is not None
        change.created_at = datetime.now(UTC) - timedelta(hours=49)
        session.commit()
        with pytest.raises(SourceDependenceConflict, match="window expired"):
            service.reverse(
                task_id,
                SourceRelationshipReversal(
                    relationship_id=accepted.relationship_id,
                    change_id=change.change_id,
                    expected_revision=1,
                    reason="too late",
                ),
            )
