"""Relationship changes invalidate the appropriate review scope."""

from test_source_dependence_contract import dependence_context  # noqa: F401

from research_agent.application.cycle_planner import _with_evidence
from research_agent.application.snapshot_service import SnapshotService
from research_agent.application.source_dependence_service import SourceDependenceService
from research_agent.domain.research import CyclePlanningBasis, SourceRelationshipCreate
from research_agent.persistence.database import SessionFactory


def test_narrow_dependence_basis_tracks_only_relevant_components(request):
    task_id, sources = request.getfixturevalue("dependence_context")
    basis = CyclePlanningBasis(reason="unverified_claim", source_ids=[sources[0]])

    def fingerprint():
        with SessionFactory() as session:
            return _with_evidence(basis, SnapshotService(session).get(task_id)).evidence_fingerprint

    def link(left, right):
        with SessionFactory() as session:
            SourceDependenceService(session).create(
                task_id,
                SourceRelationshipCreate(
                    kind="common_origin", source_a_id=left, source_b_id=right,
                    reason="Operator relationship review",
                ),
            )

    original = fingerprint()
    link(sources[2], sources[3])
    assert fingerprint() == original
    link(sources[0], sources[1])
    relevant = fingerprint()
    assert relevant != original
    link(sources[1], sources[2])
    assert fingerprint() != relevant
