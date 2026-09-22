"""Contract-negative coverage for task-scoped source dependence."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event, Thread, current_thread
from time import monotonic, sleep
from uuid import UUID, uuid4

import pytest
from conftest import purge_test_tasks
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, func, select, text

from research_agent.api.app import create_app
from research_agent.application import source_dependence_service as dependence_module
from research_agent.application.audit_service import AuditService
from research_agent.application.cycle_planner import plan_cycle_objectives
from research_agent.application.report_service import ReportService
from research_agent.application.security_capability import SecurityCapabilityDenied
from research_agent.application.security_state_service import SecurityStateTransitionService
from research_agent.application.snapshot_service import SnapshotService
from research_agent.application.source_dependence_service import (
    SourceDependenceActor,
    SourceDependenceConflict,
    SourceDependenceService,
)
from research_agent.domain.research import (
    SourceDependenceKind,
    SourceDependenceLimits,
    SourceRelationshipCreate,
    SourceRelationshipMutation,
    SourceRelationshipReversal,
)
from research_agent.domain.security import SecurityActor, SecurityReasonCode, SecurityState
from research_agent.persistence.database import SessionFactory, engine
from research_agent.persistence.models import (
    ResearchEventRecord,
    ResearchSourceRecord,
    SecurityStateRecord,
    SecurityTransitionRecord,
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


@pytest.fixture
def normal_security_state():
    actor_id = "source-dependence-ordering-test"
    with engine.begin() as connection:
        original = dict(
            connection.execute(
                text("SELECT * FROM security_state WHERE id = 1")
            ).mappings().one()
        )
        connection.execute(
            text("UPDATE security_state SET state='normal', version=1 WHERE id=1")
        )
    try:
        yield actor_id
    finally:
        with engine.begin() as connection:
            connection.execute(
                delete(SecurityTransitionRecord).where(
                    SecurityTransitionRecord.actor_id == actor_id
                )
            )
            connection.execute(
                text(
                    "UPDATE security_state SET state=:state, version=:version, "
                    "updated_at=:updated_at, authority_epoch_id=:authority_epoch_id, "
                    "recovery_bootstrap_pending=:recovery_bootstrap_pending, "
                    "recovery_bootstrap_started_at=:recovery_bootstrap_started_at, "
                    "recovery_bootstrap_from_state=:recovery_bootstrap_from_state, "
                    "recovery_bootstrap_from_version=:recovery_bootstrap_from_version "
                    "WHERE id=1"
                ),
                original,
            )


@pytest.fixture
def ordered_dependence_context(normal_security_state, dependence_context):
    return dependence_context


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


def test_retry_returns_original_result_after_later_mutation(dependence_context):
    task_id, source_ids = dependence_context
    first, second = source_ids[:2]
    operation_id = uuid4()
    request = SourceRelationshipCreate(
        derived_source_id=first,
        upstream_source_id=second,
        kind=SourceDependenceKind.DERIVED_FROM,
        reason="original command",
        operation_id=operation_id,
    )
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        accepted = service.create(task_id, request)
        service.mutate(
            task_id,
            SourceRelationshipMutation(
                relationship_id=accepted.relationship_id,
                expected_revision=1,
                operation="RETRACT",
                reason="later correction",
            ),
        )
        retried = service.create(task_id, request)
        assert retried.revision == accepted.revision == 1
        assert retried.lifecycle.value == "active"


def test_retry_rejects_changed_reason_and_actor(dependence_context):
    task_id, source_ids = dependence_context
    first, second = source_ids[:2]
    operation_id = uuid4()
    request = SourceRelationshipCreate(
        derived_source_id=first,
        upstream_source_id=second,
        kind=SourceDependenceKind.DERIVED_FROM,
        reason="trusted operator command",
        operation_id=operation_id,
    )
    with SessionFactory() as session:
        accepted = SourceDependenceService(session).create(task_id, request)
        with pytest.raises(SourceDependenceConflict, match="different content"):
            SourceDependenceService(session).create(
                task_id, request.model_copy(update={"reason": "changed reason"})
            )
        with pytest.raises(SourceDependenceConflict, match="different content"):
            SourceDependenceService(
                session, SourceDependenceActor(actor_id="api:other_operator")
            ).create(task_id, request)
        assert accepted.revision == 1


def test_mutation_retry_rejects_changed_command_and_expected_revision(dependence_context):
    task_id, source_ids = dependence_context
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        accepted = service.create(
            task_id,
            SourceRelationshipCreate(
                derived_source_id=source_ids[0],
                upstream_source_id=source_ids[1],
                kind=SourceDependenceKind.DERIVED_FROM,
                reason="mutation identity fixture",
            ),
        )
        operation_id = uuid4()
        request = SourceRelationshipMutation(
            relationship_id=accepted.relationship_id,
            expected_revision=1,
            operation="RETRACT",
            reason="same operation identity",
            operation_id=operation_id,
        )
        service.mutate(task_id, request)
        with pytest.raises(SourceDependenceConflict, match="different content"):
            service.mutate(task_id, request.model_copy(update={"operation": "SET"}))
        with pytest.raises(SourceDependenceConflict, match="different content"):
            service.mutate(task_id, request.model_copy(update={"expected_revision": 2}))


def test_reversal_retry_returns_historical_result_and_checks_target(dependence_context):
    task_id, source_ids = dependence_context
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        accepted = service.create(
            task_id,
            SourceRelationshipCreate(
                derived_source_id=source_ids[0],
                upstream_source_id=source_ids[1],
                kind=SourceDependenceKind.DERIVED_FROM,
                reason="reversal identity fixture",
            ),
        )
        retracted = service.mutate(
            task_id,
            SourceRelationshipMutation(
                relationship_id=accepted.relationship_id,
                expected_revision=1,
                operation="RETRACT",
                reason="retract before reversal",
            ),
        )
        operation_id = uuid4()
        reversal = SourceRelationshipReversal(
            relationship_id=accepted.relationship_id,
            change_id=retracted.latest_change_id,
            expected_revision=2,
            reason="restore after review",
            operation_id=operation_id,
        )
        reversed_state = service.reverse(task_id, reversal)
        service.mutate(
            task_id,
            SourceRelationshipMutation(
                relationship_id=accepted.relationship_id,
                expected_revision=3,
                operation="RETRACT",
                reason="later state change",
            ),
        )
        retried = service.reverse(task_id, reversal)
        assert retried == reversed_state
        with pytest.raises(SourceDependenceConflict, match="different content"):
            service.reverse(
                task_id,
                reversal.model_copy(update={"change_id": accepted.latest_change_id}),
            )


@pytest.mark.parametrize(
    "metadata_expression",
    [
        "jsonb_set(command_request, '{version}', '99'::jsonb)",
        "jsonb_set(command_request, '{unexpected}', 'true'::jsonb, true)",
    ],
)
def test_retry_rejects_unknown_or_changed_command_schema(dependence_context, metadata_expression):
    task_id, source_ids = dependence_context
    operation_id = uuid4()
    request = SourceRelationshipCreate(
        derived_source_id=source_ids[0],
        upstream_source_id=source_ids[1],
        kind=SourceDependenceKind.DERIVED_FROM,
        reason="command schema fixture",
        operation_id=operation_id,
    )
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        service.create(task_id, request)
        session.execute(
            text(
                "UPDATE source_relationship_changes SET command_request = "
                f"{metadata_expression} WHERE operation_id = :operation_id"
            ),
            {"operation_id": operation_id},
        )
        session.commit()
        with pytest.raises(SourceDependenceConflict, match="different content"):
            service.create(task_id, request)


def test_set_retry_preserves_omitted_defaults_after_later_mutation(dependence_context):
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
                reason="initial edge",
            ),
        )
        operation_id = uuid4()
        set_request = SourceRelationshipMutation(
            relationship_id=accepted.relationship_id,
            expected_revision=1,
            operation="SET",
            lifecycle="retracted",
            reason="temporary correction",
            operation_id=operation_id,
        )
        retracted = service.mutate(task_id, set_request)
        restored = service.reverse(
            task_id,
            SourceRelationshipReversal(
                relationship_id=accepted.relationship_id,
                change_id=retracted.latest_change_id,
                expected_revision=2,
                reason="restore edge",
            ),
        )
        retried = service.mutate(task_id, set_request)
        assert restored.revision == 3
        assert retried.revision == 2
        assert retried.lifecycle.value == "retracted"


def test_legacy_change_without_command_metadata_is_not_replayed(dependence_context):
    task_id, source_ids = dependence_context
    first, second = source_ids[:2]
    operation_id = uuid4()
    request = SourceRelationshipCreate(
        derived_source_id=first,
        upstream_source_id=second,
        kind=SourceDependenceKind.DERIVED_FROM,
        reason="legacy compatibility probe",
        operation_id=operation_id,
    )
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        service.create(task_id, request)
        session.execute(
            text(
                "UPDATE source_relationship_changes "
                "SET command_request = NULL WHERE operation_id = :operation_id"
            ),
            {"operation_id": operation_id},
        )
        session.commit()
        with pytest.raises(SourceDependenceConflict, match="different content"):
            service.create(task_id, request)


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
        service.create(
            task_id,
            SourceRelationshipCreate(
                source_a_id=third,
                source_b_id=first,
                kind=SourceDependenceKind.COMMON_ORIGIN,
                reason="pairwise origin triangle",
            ),
        )
        projection = service.project(task_id, [first])
        assert projection.complete is True
        assert projection.invalid is False
        assert projection.unknown_dependence is True
        assert third in projection.visited_source_ids
        assert len(projection.examined_relationships) == 3


def test_snapshot_bounds_omitted_root_frontier(dependence_context, monkeypatch):
    task_id, _ = dependence_context
    limits = SourceDependenceLimits(
        max_roots=2,
        max_visited_sources=2,
        max_examined_relationships=10,
        max_hops=8,
        max_frontier_sources=1,
    )
    monkeypatch.setattr(SourceDependenceService, "LIMITS", limits)
    with SessionFactory() as session:
        snapshot = SnapshotService(session).get(task_id)
        assert snapshot.source_dependence is not None
        assert snapshot.source_dependence.truncated is True
        assert snapshot.source_dependence.overflow_reason == "node_limit"
        assert len(snapshot.source_dependence.frontier_source_ids) == 1
        assert snapshot.source_dependence.frontier_omitted is True


def test_report_and_planner_fingerprints_change_with_relationship_graph(dependence_context):
    task_id, source_ids = dependence_context
    with SessionFactory() as session:
        before_report = ReportService().build(SnapshotService(session).get(task_id))
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        first = service.create(
            task_id,
            SourceRelationshipCreate(
                source_a_id=source_ids[0],
                source_b_id=source_ids[1],
                kind=SourceDependenceKind.COMMON_ORIGIN,
                reason="fingerprint relationship one",
            ),
        )
    with SessionFactory() as session:
        one_edge_snapshot = SnapshotService(session).get(task_id)
        one_edge_report = ReportService().build(one_edge_snapshot)
        _, one_edge_basis = plan_cycle_objectives(one_edge_snapshot)
    with SessionFactory() as session:
        SourceDependenceService(session).create(
            task_id,
            SourceRelationshipCreate(
                source_a_id=source_ids[1],
                source_b_id=source_ids[2],
                kind=SourceDependenceKind.COMMON_ORIGIN,
                reason="fingerprint relationship two",
            ),
        )
    with SessionFactory() as session:
        two_edge_snapshot = SnapshotService(session).get(task_id)
        two_edge_report = ReportService().build(two_edge_snapshot)
        _, two_edge_basis = plan_cycle_objectives(two_edge_snapshot)
    one_edge_dependence_basis = next(
        basis for basis in one_edge_basis if basis.reason == "source_dependence_unknown"
    )
    two_edge_dependence_basis = next(
        basis for basis in two_edge_basis if basis.reason == "source_dependence_unknown"
    )
    assert one_edge_report.review_evidence_fingerprint != before_report.review_evidence_fingerprint
    assert (
        two_edge_report.review_evidence_fingerprint
        != one_edge_report.review_evidence_fingerprint
    )
    assert (
        one_edge_dependence_basis.evidence_fingerprint
        != two_edge_dependence_basis.evidence_fingerprint
    )
    assert first.relationship_id in {
        relationship.relationship_id
        for relationship in one_edge_snapshot.source_dependence.examined_relationships
    }


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


def test_history_rejects_broken_revision_chain_without_repair(dependence_context):
    task_id, source_ids = dependence_context
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        accepted = service.create(
            task_id,
            SourceRelationshipCreate(
                derived_source_id=source_ids[0],
                upstream_source_id=source_ids[1],
                kind=SourceDependenceKind.DERIVED_FROM,
                reason="history integrity fixture",
            ),
        )
        changed = service.mutate(
            task_id,
            SourceRelationshipMutation(
                relationship_id=accepted.relationship_id,
                expected_revision=1,
                operation="RETRACT",
                reason="history correction",
            ),
        )
        row = session.get(SourceRelationshipChangeRecord, changed.latest_change_id)
        assert row is not None
        row.previous_state = {**row.previous_state, "lifecycle": "retracted"}
        session.commit()
        tampered_state = dict(row.previous_state)
        with pytest.raises(SourceDependenceConflict, match="history integrity"):
            service.history(task_id, accepted.relationship_id)
        session.refresh(row)
        assert row.previous_state == tampered_state


def test_history_rejects_current_projection_head_mismatch(dependence_context):
    task_id, source_ids = dependence_context
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        accepted = service.create(
            task_id,
            SourceRelationshipCreate(
                derived_source_id=source_ids[0],
                upstream_source_id=source_ids[1],
                kind=SourceDependenceKind.DERIVED_FROM,
                reason="head integrity fixture",
            ),
        )
        projection = session.get(SourceRelationshipRecord, accepted.relationship_id)
        assert projection is not None
        projection.revision = 2
        session.commit()
        with pytest.raises(SourceDependenceConflict, match="history integrity"):
            service.history(task_id, accepted.relationship_id)
        session.refresh(projection)
        assert projection.revision == 2


def test_history_rejects_missing_head_change_without_repair(dependence_context):
    task_id, source_ids = dependence_context
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        accepted = service.create(
            task_id,
            SourceRelationshipCreate(
                derived_source_id=source_ids[0],
                upstream_source_id=source_ids[1],
                kind=SourceDependenceKind.DERIVED_FROM,
                reason="missing history fixture",
            ),
        )
        session.delete(session.get(SourceRelationshipChangeRecord, accepted.latest_change_id))
        session.commit()
        assert session.get(SourceRelationshipChangeRecord, accepted.latest_change_id) is None
        with pytest.raises(SourceDependenceConflict, match="history integrity"):
            service.history(task_id, accepted.relationship_id)
        assert session.get(SourceRelationshipChangeRecord, accepted.latest_change_id) is None


def test_history_rejects_revision_gap_without_repair(dependence_context):
    task_id, source_ids = dependence_context
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        accepted = service.create(
            task_id,
            SourceRelationshipCreate(
                derived_source_id=source_ids[0],
                upstream_source_id=source_ids[1],
                kind=SourceDependenceKind.DERIVED_FROM,
                reason="revision gap fixture",
            ),
        )
        changed = service.mutate(
            task_id,
            SourceRelationshipMutation(
                relationship_id=accepted.relationship_id,
                expected_revision=1,
                operation="RETRACT",
                reason="revision gap correction",
            ),
        )
        session.delete(session.get(SourceRelationshipChangeRecord, accepted.latest_change_id))
        session.commit()
        with pytest.raises(SourceDependenceConflict, match="history integrity"):
            service.history(task_id, accepted.relationship_id)
        assert session.get(SourceRelationshipChangeRecord, accepted.latest_change_id) is None
        assert session.get(SourceRelationshipChangeRecord, changed.latest_change_id) is not None


@pytest.mark.parametrize("identity_field", ["relationship_id", "task_id"])
def test_history_rejects_result_state_identity_mismatch(dependence_context, identity_field):
    task_id, source_ids = dependence_context
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        accepted = service.create(
            task_id,
            SourceRelationshipCreate(
                derived_source_id=source_ids[0],
                upstream_source_id=source_ids[1],
                kind=SourceDependenceKind.DERIVED_FROM,
                reason="identity mismatch fixture",
            ),
        )
        replacement_id = uuid4()
        row = session.get(SourceRelationshipChangeRecord, accepted.latest_change_id)
        assert row is not None
        row.resulting_state = {
            **row.resulting_state,
            identity_field: str(replacement_id),
        }
        session.commit()
        with pytest.raises(SourceDependenceConflict, match="history integrity"):
            service.history(task_id, accepted.relationship_id)
        session.refresh(row)
        assert row.resulting_state[identity_field] == str(replacement_id)


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
        for index in range(2):
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


def test_projection_distinct_edge_budget_accepts_exact_and_rejects_one_over(
    dependence_context,
):
    task_id, source_ids = dependence_context
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        for index in range(2):
            service.create(
                task_id,
                SourceRelationshipCreate(
                    source_a_id=source_ids[index],
                    source_b_id=source_ids[index + 1],
                    kind=SourceDependenceKind.COMMON_ORIGIN,
                    reason=f"edge budget {index}",
                ),
            )
        service.LIMITS = SourceDependenceLimits(
            max_roots=4,
            max_visited_sources=4,
            max_examined_relationships=2,
            max_hops=8,
            max_frontier_sources=2,
        )
        exact = service.project(task_id, [source_ids[0]])
        assert exact.complete is True
        assert len(exact.examined_relationships) == 2
        service.create(
            task_id,
            SourceRelationshipCreate(
                source_a_id=source_ids[2],
                source_b_id=source_ids[3],
                kind=SourceDependenceKind.COMMON_ORIGIN,
                reason="edge budget one over",
            ),
        )
        excess = service.project(task_id, [source_ids[0]])
        assert excess.complete is False
        assert excess.overflow_reason == "edge_limit"
        assert len(excess.examined_relationships) == 2


def test_projection_uses_one_node_budget_across_roots(dependence_context):
    task_id, source_ids = dependence_context
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        for left, right in ((source_ids[0], source_ids[1]), (source_ids[2], source_ids[3])):
            service.create(
                task_id,
                SourceRelationshipCreate(
                    source_a_id=left,
                    source_b_id=right,
                    kind=SourceDependenceKind.COMMON_ORIGIN,
                    reason="shared node budget",
                ),
            )
        service.LIMITS = SourceDependenceLimits(
            max_roots=4,
            max_visited_sources=3,
            max_examined_relationships=10,
            max_hops=8,
            max_frontier_sources=1,
        )
        projection = service.project(task_id, [source_ids[0], source_ids[2]])
        assert projection.truncated is True
        assert projection.overflow_reason == "node_limit"
        assert len(projection.visited_source_ids) == 3
        assert len(projection.frontier_source_ids) == 1
        assert projection.frontier_source_ids[0] in source_ids[1:4:2]


def test_projection_node_and_depth_budgets_accept_exact_boundary(dependence_context):
    task_id, source_ids = dependence_context
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        for index in range(2):
            service.create(
                task_id,
                SourceRelationshipCreate(
                    source_a_id=source_ids[index],
                    source_b_id=source_ids[index + 1],
                    kind=SourceDependenceKind.COMMON_ORIGIN,
                    reason="exact traversal boundary",
                ),
            )
        service.LIMITS = SourceDependenceLimits(
            max_roots=4,
            max_visited_sources=3,
            max_examined_relationships=10,
            max_hops=2,
            max_frontier_sources=2,
        )
        exact = service.project(task_id, [source_ids[0]])
        assert exact.complete is True
        assert len(exact.visited_source_ids) == 3
        assert exact.frontier_source_ids == []


def test_projection_bounds_frontier_and_reports_omitted_entries(dependence_context):
    task_id, source_ids = dependence_context
    with SessionFactory() as session:
        extra_ids = [uuid4() for _ in range(20)]
        now = datetime.now(UTC)
        session.add_all(
            ResearchSourceRecord(
                id=source_id,
                task_id=task_id,
                source_type="web_page",
                title=f"Fanout source {index}",
                uri=f"https://fanout.example/{index}",
                publisher="fixture",
                content="fanout content",
                content_hash=f"{index + 100:064x}",
                reliability_score=0.5,
                observed_at=now,
                source_metadata={},
            )
            for index, source_id in enumerate(extra_ids)
        )
        session.commit()
        service = SourceDependenceService(session)
        for index, source_id in enumerate([*source_ids[1:], *extra_ids]):
            service.create(
                task_id,
                SourceRelationshipCreate(
                    source_a_id=source_ids[0],
                    source_b_id=source_id,
                    kind=SourceDependenceKind.COMMON_ORIGIN,
                    reason=f"fanout {index}",
                ),
            )
        service.LIMITS = SourceDependenceLimits(
            max_roots=4,
            max_visited_sources=1,
            max_examined_relationships=100,
            max_hops=8,
            max_frontier_sources=2,
        )
        projection = service.project(task_id, [source_ids[0]])
        assert len(projection.frontier_source_ids) == 2
        assert projection.frontier_omitted is True
        assert projection.truncated is True
        assert projection.frontier_source_ids == service.project(
            task_id, [source_ids[0]]
        ).frontier_source_ids


def test_projection_marks_examined_directed_cycle_invalid(dependence_context):
    task_id, source_ids = dependence_context
    first, second, third = source_ids[:3]
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        relationships = []
        for left, right in ((first, second), (second, third), (third, first)):
            relationships.append(
                service.create(
                    task_id,
                    SourceRelationshipCreate(
                        source_a_id=left,
                        source_b_id=right,
                        kind=SourceDependenceKind.COMMON_ORIGIN,
                        reason="cycle-detection fixture",
                    ),
                )
            )
        for derived_id, upstream_id, relationship in (
            (first, second, relationships[0]),
            (second, third, relationships[1]),
            (third, first, relationships[2]),
        ):
            direction = (
                "low_to_high"
                if derived_id.int < upstream_id.int
                else "high_to_low"
            )
            session.execute(
                text(
                    "UPDATE source_relationships "
                    "SET kind = 'derived_from', direction = :direction "
                    "WHERE relationship_id = :relationship_id"
                ),
                {"direction": direction, "relationship_id": relationship.relationship_id},
            )
        session.commit()
        projection = service.project(task_id, [first])
        assert projection.invalid is True
        assert projection.invalid_reason == "directed_cycle"
        assert projection.complete is False
        snapshot = SnapshotService(session).get(task_id)
        report = ReportService().build(snapshot)
        assert report.source_dependence is not None
        assert report.source_dependence.invalid is True
        assert any("Invalid directed source-dependence" in item for item in report.limitations)
        objectives, _ = plan_cycle_objectives(snapshot)
        assert any("invalid directed source-dependence" in item for item in objectives)


@pytest.mark.parametrize("read_path", ["projection", "snapshot"])
def test_graph_read_holds_task_lock_against_concurrent_relationship_mutation(
    dependence_context, read_path
):
    task_id, source_ids = dependence_context
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        relationship = service.create(
            task_id,
            SourceRelationshipCreate(
                source_a_id=source_ids[0],
                source_b_id=source_ids[1],
                kind=SourceDependenceKind.COMMON_ORIGIN,
                reason="stable traversal fixture",
            ),
        )

    adjacency_read = Event()
    allow_reader = Event()
    writer_lock_requested = Event()
    reader_finished = Event()
    writer_finished = Event()
    result = []
    errors = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        if (
            current_thread().name == "dependence-writer"
            and "research_tasks" in statement
            and "FOR UPDATE" in statement
        ):
            writer_lock_requested.set()

    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        if (
            current_thread().name == "dependence-reader"
            and "FROM source_relationships" in statement
            and "LIMIT" in statement
            and not adjacency_read.is_set()
        ):
            adjacency_read.set()
            if not allow_reader.wait(5):
                raise TimeoutError("test did not release the traversal reader")

    def reader():
        try:
            with SessionFactory() as session:
                if read_path == "projection":
                    projection = SourceDependenceService(session).project(task_id, [source_ids[0]])
                else:
                    projection = SnapshotService(session).get(task_id).source_dependence
                assert projection is not None
                result.append(projection)
            reader_finished.set()
        except Exception as exc:  # surfaced in the main test thread
            errors.append(exc)
            reader_finished.set()

    def writer():
        try:
            with SessionFactory() as session:
                SourceDependenceService(session).mutate(
                    task_id,
                    SourceRelationshipMutation(
                        relationship_id=relationship.relationship_id,
                        expected_revision=1,
                        operation="RETRACT",
                        reason="concurrent mutation",
                    ),
                )
            writer_finished.set()
        except Exception as exc:  # surfaced in the main test thread
            errors.append(exc)
            writer_finished.set()

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    event.listen(engine, "after_cursor_execute", after_cursor_execute)
    reader_thread = Thread(target=reader, name="dependence-reader")
    writer_thread = Thread(target=writer, name="dependence-writer")
    try:
        reader_thread.start()
        assert adjacency_read.wait(5)
        writer_thread.start()
        assert writer_lock_requested.wait(5)
        allow_reader.set()
        reader_thread.join(5)
        writer_thread.join(5)
    finally:
        allow_reader.set()
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
        event.remove(engine, "after_cursor_execute", after_cursor_execute)
    assert not reader_thread.is_alive()
    assert not writer_thread.is_alive()
    assert not errors
    assert reader_finished.is_set() and writer_finished.is_set()
    assert result[0].examined_relationships[0].lifecycle.value == "active"
    with SessionFactory() as session:
        current = SourceDependenceService(session).get(task_id, relationship.relationship_id)
        assert current.lifecycle.value == "retracted"


@pytest.mark.parametrize("budget", ["nodes", "edges"])
def test_cycle_proof_budget_overflow_rejects_without_partial_write(dependence_context, budget):
    task_id, source_ids = dependence_context
    upstream, branch_a, branch_b, proposed_derived = source_ids
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        for branch in (branch_a, branch_b):
            existing = service.create(
                task_id,
                SourceRelationshipCreate(
                    source_a_id=upstream,
                    source_b_id=branch,
                    kind=SourceDependenceKind.COMMON_ORIGIN,
                    reason="bounded cycle proof fixture",
                ),
            )
            direction = "low_to_high" if upstream.int < branch.int else "high_to_low"
            session.execute(
                text(
                    "UPDATE source_relationships "
                    "SET kind = 'derived_from', direction = :direction "
                    "WHERE relationship_id = :relationship_id"
                ),
                {"direction": direction, "relationship_id": existing.relationship_id},
            )
        session.commit()
        limits = {"max_visited_sources": 1} if budget == "nodes" else {
            "max_examined_relationships": 1
        }
        service.LIMITS = service.LIMITS.model_copy(update=limits)
        before_relationships = session.scalar(
            select(func.count()).select_from(SourceRelationshipRecord).where(
                SourceRelationshipRecord.task_id == task_id
            )
        )
        before_changes = session.scalar(
            select(func.count()).select_from(SourceRelationshipChangeRecord).where(
                SourceRelationshipChangeRecord.task_id == task_id
            )
        )
        before_events = session.scalar(
            select(func.count()).select_from(ResearchEventRecord).where(
                ResearchEventRecord.task_id == task_id,
                ResearchEventRecord.event_type == "source.dependence_changed",
            )
        )
        with pytest.raises(SourceDependenceConflict, match="prevents cycle proof"):
            service.create(
                task_id,
                SourceRelationshipCreate(
                    derived_source_id=proposed_derived,
                    upstream_source_id=upstream,
                    kind=SourceDependenceKind.DERIVED_FROM,
                    reason="must fail closed on incomplete proof",
                ),
            )
        after_relationships = session.scalar(
            select(func.count()).select_from(SourceRelationshipRecord).where(
                SourceRelationshipRecord.task_id == task_id
            )
        )
        after_changes = session.scalar(
            select(func.count()).select_from(SourceRelationshipChangeRecord).where(
                SourceRelationshipChangeRecord.task_id == task_id
            )
        )
        after_events = session.scalar(
            select(func.count()).select_from(ResearchEventRecord).where(
                ResearchEventRecord.task_id == task_id,
                ResearchEventRecord.event_type == "source.dependence_changed",
            )
        )
        assert after_relationships == before_relationships
        assert after_changes == before_changes
        assert after_events == before_events


def _wait_until_blocked(waiter_pid: int, blocker_pid: int) -> None:
    deadline = monotonic() + 5
    with engine.connect() as connection:
        while monotonic() < deadline:
            blockers = connection.scalar(
                text("SELECT pg_blocking_pids(:pid)"), {"pid": waiter_pid}
            )
            if blocker_pid in blockers:
                return
            sleep(0.01)
    raise AssertionError("Expected PostgreSQL row-lock blocking was not observed")


def test_concurrent_reciprocal_derived_edges_serialize_to_one_valid_change(
    ordered_dependence_context,
):
    task_id, source_ids = ordered_dependence_context
    first, second = source_ids[:2]
    winner_locked, release_winner = Event(), Event()
    waiter_requested = Event()
    pids = {}

    def before_execute(conn, cursor, statement, params, context, many):
        if (
            current_thread().name.startswith("dependence-reciprocal_")
            and current_thread().name.endswith("_1")
            and "FROM research_tasks" in statement
            and "FOR UPDATE" in statement
        ):
            waiter_requested.set()

    def after_execute(conn, cursor, statement, params, context, many):
        if (
            current_thread().name.startswith("dependence-reciprocal_")
            and current_thread().name.endswith("_0")
            and "FROM research_tasks" in statement
            and "FOR UPDATE" in statement
            and not winner_locked.is_set()
        ):
            winner_locked.set()
            if not release_winner.wait(10):
                raise TimeoutError("reciprocal-edge winner was not released")

    def submit(role, derived_id, upstream_id):
        with SessionFactory() as session:
            pids[role] = session.connection().scalar(text("SELECT pg_backend_pid()"))
            return SourceDependenceService(session).create(
                task_id,
                SourceRelationshipCreate(
                    derived_source_id=derived_id,
                    upstream_source_id=upstream_id,
                    kind=SourceDependenceKind.DERIVED_FROM,
                    reason=f"concurrent reciprocal attempt {role}",
                ),
            )

    event.listen(engine, "before_cursor_execute", before_execute)
    event.listen(engine, "after_cursor_execute", after_execute)
    try:
        with ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="dependence-reciprocal"
        ) as pool:
            first_attempt = pool.submit(submit, "winner", first, second)
            assert winner_locked.wait(5)
            second_attempt = pool.submit(submit, "waiter", second, first)
            assert waiter_requested.wait(5)
            _wait_until_blocked(pids["waiter"], pids["winner"])
            assert not second_attempt.done()
            release_winner.set()
            accepted = first_attempt.result(timeout=10)
            with pytest.raises(SourceDependenceConflict, match="would create a cycle"):
                second_attempt.result(timeout=10)
    finally:
        release_winner.set()
        event.remove(engine, "before_cursor_execute", before_execute)
        event.remove(engine, "after_cursor_execute", after_execute)

    with SessionFactory() as session:
        relationships = session.scalars(
            select(SourceRelationshipRecord).where(
                SourceRelationshipRecord.task_id == task_id
            )
        ).all()
        changes = session.scalars(
            select(SourceRelationshipChangeRecord).where(
                SourceRelationshipChangeRecord.task_id == task_id
            )
        ).all()
        events = session.scalars(
            select(ResearchEventRecord).where(
                ResearchEventRecord.task_id == task_id,
                ResearchEventRecord.event_type == "source.dependence_changed",
            )
        ).all()
    assert len(relationships) == len(changes) == len(events) == 1
    assert relationships[0].relationship_id == accepted.relationship_id
    assert changes[0].revision == 1 and changes[0].operation == "CREATE"


@pytest.mark.parametrize("winner", ["mutation", "lockdown"])
def test_source_dependence_mutation_and_lockdown_have_one_serialized_winner(
    ordered_dependence_context, normal_security_state, winner
):
    task_id, source_ids = ordered_dependence_context
    mutation_locked, lockdown_locked = Event(), Event()
    release_winner, waiter_requested = Event(), Event()
    pids = {}

    def before_execute(conn, cursor, statement, params, context, many):
        name = current_thread().name
        if name.endswith("_1") and (
            (
                winner == "mutation"
                and "FROM security_state" in statement
                and "FOR UPDATE" in statement
            )
            or (
                winner == "lockdown"
                and "FROM security_state" in statement
                and "FOR SHARE" in statement
            )
        ):
            waiter_requested.set()

    def after_execute(conn, cursor, statement, params, context, many):
        name = current_thread().name
        if (
            winner == "mutation"
            and name.endswith("_0")
            and "FROM security_state" in statement
            and "FOR SHARE" in statement
        ):
            if not mutation_locked.is_set():
                mutation_locked.set()
                if not release_winner.wait(10):
                    raise TimeoutError("source mutation was not released")
        if (
            winner == "lockdown"
            and name.endswith("_0")
            and "FROM security_state" in statement
            and "FOR UPDATE" in statement
        ):
            if not lockdown_locked.is_set():
                lockdown_locked.set()
                if not release_winner.wait(10):
                    raise TimeoutError("lockdown transition was not released")

    def mutate():
        with SessionFactory() as session:
            pids["mutation"] = session.connection().scalar(text("SELECT pg_backend_pid()"))
            try:
                return SourceDependenceService(session).create(
                    task_id,
                    SourceRelationshipCreate(
                        source_a_id=source_ids[0],
                        source_b_id=source_ids[1],
                        kind=SourceDependenceKind.COMMON_ORIGIN,
                        reason="mutation/lockdown ordering regression",
                    ),
                )
            except SecurityCapabilityDenied as exc:
                return exc

    def lockdown():
        with SessionFactory() as session:
            pids["lockdown"] = session.connection().scalar(text("SELECT pg_backend_pid()"))
            return SecurityStateTransitionService(session).transition(
                expected_version=1,
                requested_state=SecurityState.LOCKDOWN,
                actor_type=SecurityActor.LOCAL_OPERATOR,
                actor_id=normal_security_state,
                reason_code=SecurityReasonCode.OPERATOR_LOCKDOWN,
            )

    event.listen(engine, "before_cursor_execute", before_execute)
    event.listen(engine, "after_cursor_execute", after_execute)
    try:
        with ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="dependence-lockdown-order"
        ) as pool:
            first = pool.submit(mutate if winner == "mutation" else lockdown)
            winner_gate = mutation_locked if winner == "mutation" else lockdown_locked
            waiter = "lockdown" if winner == "mutation" else "mutation"
            blocker = "mutation" if winner == "mutation" else "lockdown"
            try:
                assert winner_gate.wait(5)
                second = pool.submit(lockdown if winner == "mutation" else mutate)
                assert waiter_requested.wait(5)
                _wait_until_blocked(pids[waiter], pids[blocker])
                assert not second.done()
            finally:
                release_winner.set()
            first_result = first.result(timeout=10)
            second_result = second.result(timeout=10)
            mutation_result = first_result if winner == "mutation" else second_result
            lockdown_result = first_result if winner == "lockdown" else second_result
            if winner == "lockdown":
                assert isinstance(mutation_result, SecurityCapabilityDenied)
            else:
                assert mutation_result.relationship_id
            assert lockdown_result.state is SecurityState.LOCKDOWN
    finally:
        release_winner.set()
        event.remove(engine, "before_cursor_execute", before_execute)
        event.remove(engine, "after_cursor_execute", after_execute)

    with SessionFactory() as session:
        assert session.get(SecurityStateRecord, 1).state == "lockdown"
        relationships = session.scalars(
            select(SourceRelationshipRecord).where(
                SourceRelationshipRecord.task_id == task_id
            )
        ).all()
        changes = session.scalars(
            select(SourceRelationshipChangeRecord).where(
                SourceRelationshipChangeRecord.task_id == task_id
            )
        ).all()
        events = session.scalars(
            select(ResearchEventRecord).where(
                ResearchEventRecord.task_id == task_id,
                ResearchEventRecord.event_type == "source.dependence_changed",
            )
        ).all()
        transitions = session.scalars(
            select(SecurityTransitionRecord).where(
                SecurityTransitionRecord.actor_id == normal_security_state
            )
        ).all()
    expected_mutations = 1 if winner == "mutation" else 0
    assert len(relationships) == len(changes) == len(events) == expected_mutations
    assert len(transitions) == 1


def test_cycle_proof_overflow_rolls_back_before_waiting_lockdown_commits(
    ordered_dependence_context, normal_security_state, monkeypatch
):
    task_id, source_ids = ordered_dependence_context
    upstream, branch_a, branch_b, proposed_derived = source_ids
    with SessionFactory() as session:
        service = SourceDependenceService(session)
        for branch in (branch_a, branch_b):
            relationship = service.create(
                task_id,
                SourceRelationshipCreate(
                    source_a_id=upstream,
                    source_b_id=branch,
                    kind=SourceDependenceKind.COMMON_ORIGIN,
                    reason="cycle-proof overflow/lockdown race fixture",
                ),
            )
            direction = "low_to_high" if upstream.int < branch.int else "high_to_low"
            session.execute(
                text(
                    "UPDATE source_relationships "
                    "SET kind='derived_from', direction=:direction "
                    "WHERE relationship_id=:relationship_id"
                ),
                {"direction": direction, "relationship_id": relationship.relationship_id},
            )
        session.commit()

    monkeypatch.setattr(
        SourceDependenceService,
        "LIMITS",
        SourceDependenceService.LIMITS.model_copy(
            update={"max_examined_relationships": 1}
        ),
    )
    with SessionFactory() as session:
        before_relationships = [
            (item.relationship_id, item.revision, item.latest_change_id)
            for item in session.scalars(
                select(SourceRelationshipRecord)
                .where(SourceRelationshipRecord.task_id == task_id)
                .order_by(SourceRelationshipRecord.relationship_id)
            )
        ]
        before_changes = session.scalar(
            select(func.count()).select_from(SourceRelationshipChangeRecord).where(
                SourceRelationshipChangeRecord.task_id == task_id
            )
        )
        before_events = session.scalar(
            select(func.count()).select_from(ResearchEventRecord).where(
                ResearchEventRecord.task_id == task_id,
                ResearchEventRecord.event_type == "source.dependence_changed",
            )
        )

    proof_started, lockdown_requested, release_proof = Event(), Event(), Event()
    pids = {}

    def before_execute(conn, cursor, statement, params, context, many):
        if (
            current_thread().name.endswith("_1")
            and "FROM security_state" in statement
            and "FOR UPDATE" in statement
        ):
            lockdown_requested.set()

    def after_execute(conn, cursor, statement, params, context, many):
        if (
            current_thread().name.endswith("_0")
            and "FROM source_relationships" in statement
            and "LIMIT" in statement
            and not proof_started.is_set()
        ):
            proof_started.set()
            if not release_proof.wait(10):
                raise TimeoutError("cycle-proof query was not released")

    def attempt_overflow():
        with SessionFactory() as session:
            pids["mutation"] = session.connection().scalar(text("SELECT pg_backend_pid()"))
            try:
                SourceDependenceService(session).create(
                    task_id,
                    SourceRelationshipCreate(
                        derived_source_id=proposed_derived,
                        upstream_source_id=upstream,
                        kind=SourceDependenceKind.DERIVED_FROM,
                        reason="must fail closed while lockdown waits",
                    ),
                )
            except SourceDependenceConflict as exc:
                return exc
            raise AssertionError("incomplete cycle proof unexpectedly allowed the write")

    def lockdown():
        with SessionFactory() as session:
            pids["lockdown"] = session.connection().scalar(text("SELECT pg_backend_pid()"))
            return SecurityStateTransitionService(session).transition(
                expected_version=1,
                requested_state=SecurityState.LOCKDOWN,
                actor_type=SecurityActor.LOCAL_OPERATOR,
                actor_id=normal_security_state,
                reason_code=SecurityReasonCode.OPERATOR_LOCKDOWN,
            )

    event.listen(engine, "before_cursor_execute", before_execute)
    event.listen(engine, "after_cursor_execute", after_execute)
    try:
        with ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="dependence-overflow-lockdown"
        ) as pool:
            mutation_future = pool.submit(attempt_overflow)
            try:
                assert proof_started.wait(5)
                lockdown_future = pool.submit(lockdown)
                assert lockdown_requested.wait(5)
                _wait_until_blocked(pids["lockdown"], pids["mutation"])
            finally:
                release_proof.set()
            failure = mutation_future.result(timeout=10)
            transition = lockdown_future.result(timeout=10)
    finally:
        release_proof.set()
        event.remove(engine, "before_cursor_execute", before_execute)
        event.remove(engine, "after_cursor_execute", after_execute)

    assert "prevents cycle proof" in str(failure)
    assert transition.state is SecurityState.LOCKDOWN
    with SessionFactory() as session:
        after_relationships = [
            (item.relationship_id, item.revision, item.latest_change_id)
            for item in session.scalars(
                select(SourceRelationshipRecord)
                .where(SourceRelationshipRecord.task_id == task_id)
                .order_by(SourceRelationshipRecord.relationship_id)
            )
        ]
        after_changes = session.scalar(
            select(func.count()).select_from(SourceRelationshipChangeRecord).where(
                SourceRelationshipChangeRecord.task_id == task_id
            )
        )
        after_events = session.scalar(
            select(func.count()).select_from(ResearchEventRecord).where(
                ResearchEventRecord.task_id == task_id,
                ResearchEventRecord.event_type == "source.dependence_changed",
            )
        )
        assert session.get(SecurityStateRecord, 1).state == "lockdown"
        assert session.scalar(
            select(func.count()).select_from(SecurityTransitionRecord).where(
                SecurityTransitionRecord.actor_id == normal_security_state
            )
        ) == 1
    assert after_relationships == before_relationships
    assert after_changes == before_changes
    assert after_events == before_events


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
