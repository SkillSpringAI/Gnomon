"""Stopping readiness must retain uncertainty surfaced by planning."""

from uuid import uuid4

import pytest

from research_agent.application.cycle_planner import _with_evidence, reference_fingerprint
from research_agent.application.research_service import (
    InMemoryResearchTaskRepository,
    ResearchService,
)
from research_agent.application.stopping_decision_service import StoppingDecisionService
from research_agent.domain.research import (
    CyclePlanningBasis,
    CycleStatus,
    Hypothesis,
    HypothesisAssessmentResponse,
    HypothesisAssessmentStatus,
    ObjectiveReview,
    ResearchBrief,
    utc_now,
)
from research_agent.domain.snapshot import HypothesisSnapshot


def snapshot():
    repo = InMemoryResearchTaskRepository()
    task = ResearchService(repo).create_task(ResearchBrief(title="Readiness", objective="Inspect"))
    return repo.planning_snapshot(task.id)


def items(state):
    return {
        item.code: item for item in StoppingDecisionService._readiness_from_snapshot(state, 1).items
    }


@pytest.mark.parametrize("status", list(CycleStatus))
def test_unfinished_cycle_objectives_are_outstanding(status):
    state = snapshot()
    state.task.cycles[0].status = status
    assert items(state)["unresolved_objectives"].status == (
        "satisfied" if status == CycleStatus.COMPLETED else "attention"
    )


def test_prior_cycle_objectives_remain_visible():
    state = snapshot()
    first = state.task.cycles[0]
    first.status = CycleStatus.BLOCKED
    state.task.cycles.append(
        first.model_copy(
            update={
                "number": 2,
                "status": CycleStatus.COMPLETED,
                "objectives": ["Other work"],
            }
        )
    )
    assert items(state)["unresolved_objectives"].status == "attention"


def test_unresolved_assessment_is_a_warning():
    state = snapshot()
    hypothesis = Hypothesis(label="H1", statement="A proposition")
    state.hypotheses.append(
        HypothesisSnapshot(
            hypothesis=hypothesis,
            assessment_state="assessed",
            assessment=HypothesisAssessmentResponse(
                id=uuid4(),
                task_id=state.task.id,
                hypothesis_id=hypothesis.id,
                status=HypothesisAssessmentStatus.UNRESOLVED,
                summary="Insufficient evidence",
                confidence=0.2,
                evidence_links=[],
                updated_at=utc_now(),
            ),
        )
    )
    assert items(state)["unresolved_assessment"].status == "attention"
    assert "H1" in items(state)["unresolved_assessment"].detail


def test_effective_review_controls_resolution_and_superseded_staleness():
    state = snapshot()
    cycle = state.task.cycles[0]
    cycle.status = CycleStatus.COMPLETED
    basis = _with_evidence(CyclePlanningBasis(reason="incomplete_cycle"), state)
    review = ObjectiveReview(
        objective_index=0,
        objective=cycle.objectives[0],
        revision=1,
        decision="completed",
        rationale="Reviewed",
        source_ids=[],
        claim_ids=[],
        basis=basis,
        reference_fingerprint="",
    )
    review.reference_fingerprint = reference_fingerprint(review, state)
    cycle.objective_reviews.append(review)
    assert items(state)["unresolved_objectives"].status == "satisfied"
    review.reference_fingerprint = "stale"
    assert items(state)["stale_reviews"].status == "attention"
    assert items(state)["unresolved_objectives"].status == "attention"
    replacement = review.model_copy(update={"id": uuid4(), "revision": 2})
    replacement.reference_fingerprint = reference_fingerprint(replacement, state)
    cycle.objective_reviews.append(replacement)
    assert items(state)["stale_reviews"].status == "satisfied"
    assert items(state)["unresolved_objectives"].status == "satisfied"


@pytest.mark.parametrize("invalid,truncated", [(False, False), (True, False), (False, True)])
def test_dependence_never_implies_independence(invalid, truncated):
    from research_agent.domain.research import (
        SourceDependenceLimits,
        SourceDependenceProjection,
        SourceResponse,
        SourceType,
    )

    state = snapshot()
    source = SourceResponse(
        id=uuid4(),
        task_id=state.task.id,
        source_type=SourceType.DOCUMENT,
        title="Evidence",
        content="Observation",
        uri=None,
        publisher=None,
        reliability_score=0.5,
        observed_at=utc_now(),
    )
    state.sources.append(source)
    state.source_dependence = SourceDependenceProjection(
        task_id=state.task.id,
        complete=not (invalid or truncated),
        truncated=truncated,
        invalid=invalid,
        limits=SourceDependenceLimits(),
        visited_source_ids=[source.id],
        examined_relationships=[],
        frontier_source_ids=[],
    )
    item = items(state)["dependence_unknown"]
    assert item.status == "unknown"
    assert ("incomplete or invalid" in item.detail) == (invalid or truncated)


def test_contradicting_link_warns_even_when_claim_is_not_contested():
    from research_agent.domain.research import (
        ClaimResponse,
        ClaimSourceLink,
        ClaimStatus,
        SupportType,
    )

    state = snapshot()
    claim = ClaimResponse(
        id=uuid4(),
        task_id=state.task.id,
        statement="Proposition",
        confidence=0.5,
        status=ClaimStatus.UNVERIFIED,
        created_at=utc_now(),
        source_links=[ClaimSourceLink(source_id=uuid4(), support_type=SupportType.CONTRADICTING)],
    )
    state.claims.append(claim)
    assert items(state)["contradictory_claims"].claim_ids == [claim.id]
    assert items(state)["contradictory_claims"].status == "attention"
