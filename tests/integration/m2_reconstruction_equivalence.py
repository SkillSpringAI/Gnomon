"""Deterministic M2.7 reconstruction equivalence projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from research_agent.application.migrations import MIGRATIONS_TABLE
from research_agent.application.report_service import ReportService
from research_agent.application.snapshot_service import SnapshotService

_PROJECTION_QUERIES: dict[str, tuple[str, ...]] = {
    "research": (
        'SELECT to_jsonb(t) FROM research_tasks t ORDER BY t.id',
        'SELECT to_jsonb(c) FROM research_cycles c ORDER BY c.task_id, c.cycle_number',
    ),
    "evidence_provenance": (
        'SELECT to_jsonb(s) FROM research_sources s ORDER BY s.task_id, s.observed_at, s.id',
        'SELECT to_jsonb(c) FROM research_claims c ORDER BY c.task_id, c.created_at, c.id',
        'SELECT to_jsonb(cs) FROM claim_sources cs ORDER BY cs.claim_id, cs.source_id',
    ),
    "assessments": (
        """
        SELECT to_jsonb(a)
        FROM hypothesis_assessments a
        ORDER BY a.task_id, a.hypothesis_id, a.id
        """,
        """
        SELECT to_jsonb(e)
        FROM assessment_evidence e
        ORDER BY e.assessment_id, e.claim_id
        """,
    ),
    "source_dependence": (
        """
        SELECT to_jsonb(r)
        FROM source_relationships r
        ORDER BY r.task_id, r.source_low_id, r.source_high_id, r.kind
        """,
        """
        SELECT to_jsonb(c)
        FROM source_relationship_changes c
        ORDER BY c.task_id, c.relationship_id, c.revision, c.change_id
        """,
    ),
    "memory": (
        """
        SELECT to_jsonb(m)
        FROM memory_changes m
        ORDER BY m.task_id, m.target_type, m.target_id, m.version, m.change_id
        """,
    ),
    "stopping": (
        """
        SELECT to_jsonb(d)
        FROM stopping_decisions d
        ORDER BY d.task_id, d.revision, d.decision_id
        """,
        """
        SELECT to_jsonb(c)
        FROM stopping_decision_changes c
        ORDER BY c.task_id, c.decision_id, c.revision, c.change_id
        """,
    ),
    "execution_attempts": (
        """
        SELECT to_jsonb(a)
        FROM research_cycle_attempts a
        ORDER BY a.task_id, a.cycle_id, a.started_at, a.id
        """,
    ),
    "provider_attempts": (
        """
        SELECT to_jsonb(a)
        FROM report_generation_attempts a
        ORDER BY a.task_id, a.started_at, a.operation_id
        """,
    ),
    "audit": (
        'SELECT to_jsonb(e) FROM research_events e ORDER BY e.task_id, e.created_at, e.id',
        """
        SELECT to_jsonb(e)
        FROM trusted_source_policy_events e
        ORDER BY e.created_at, e.event_id
        """,
        """
        SELECT to_jsonb(e)
        FROM provider_session_events e
        ORDER BY e.created_at, e.event_id
        """,
    ),
    "security_epoch": (
        'SELECT to_jsonb(s) FROM security_state s ORDER BY s.id',
        """
        SELECT to_jsonb(t)
        FROM security_state_transitions t
        ORDER BY t.security_state_version, t.created_at, t.transition_id
        """,
    ),
    "recovery_authorization": (
        """
        SELECT to_jsonb(c)
        FROM recovery_contexts c
        ORDER BY c.created_at, c.context_id
        """,
        """
        SELECT to_jsonb(a)
        FROM recovery_context_audit a
        ORDER BY a.created_at, a.context_id
        """,
        """
        SELECT to_jsonb(o)
        FROM operator_authorizations o
        ORDER BY o.issued_at, o.authorization_id
        """,
        """
        SELECT to_jsonb(e)
        FROM execution_authorizations e
        ORDER BY e.issued_at, e.execution_authorization_id
        """,
        """
        SELECT to_jsonb(a)
        FROM authorization_audit a
        ORDER BY a.created_at, a.artifact_type, a.artifact_id
        """,
    ),
    "migration_state": (
        f"""
        SELECT jsonb_build_object('version', m.version, 'checksum', m.checksum)
        FROM {MIGRATIONS_TABLE} m
        ORDER BY m.version
        """,
    ),
}


class ReconstructionEquivalenceMismatch(AssertionError):
    """Source and restored projections are not equivalent."""


@dataclass(frozen=True)
class ReconstructionEquivalenceProjection:
    groups: dict[str, list[Any]]
    snapshot: dict[str, Any]
    report: dict[str, Any]


def projection_for(engine: Engine, *, task_id: UUID) -> ReconstructionEquivalenceProjection:
    """Return deterministic M2 equivalence projections for one database."""
    with engine.connect() as conn:
        groups = {
            group_name: [
                row[0]
                for query in queries
                for row in conn.execute(text(query)).all()
            ]
            for group_name, queries in _PROJECTION_QUERIES.items()
        }
    with Session(engine) as session:
        snapshot = SnapshotService(session).get(task_id)
        report = ReportService().build(snapshot)
    return ReconstructionEquivalenceProjection(
        groups=groups,
        snapshot=snapshot.model_dump(mode="json"),
        report=report.model_dump(mode="json"),
    )


def assert_reconstruction_equivalent(
    source: Engine,
    restored: Engine,
    *,
    task_id: UUID,
) -> None:
    """Raise with the first changed projection group when databases differ."""
    source_projection = projection_for(source, task_id=task_id)
    restored_projection = projection_for(restored, task_id=task_id)
    if source_projection.groups != restored_projection.groups:
        for group_name in _PROJECTION_QUERIES:
            if source_projection.groups[group_name] != restored_projection.groups[group_name]:
                raise ReconstructionEquivalenceMismatch(
                    f"Projection group differs: {group_name}"
                )
        raise ReconstructionEquivalenceMismatch("Projection groups differ")
    if source_projection.snapshot != restored_projection.snapshot:
        raise ReconstructionEquivalenceMismatch("Snapshot projection differs")
    if source_projection.report != restored_projection.report:
        raise ReconstructionEquivalenceMismatch("Report projection differs")
