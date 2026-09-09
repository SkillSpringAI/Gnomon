"""Deterministic, evidence-aware planning. No text inference or tool execution."""

from research_agent.domain.research import (
    ClaimResponse,
    ClaimStatus,
    CyclePlanningBasis,
    CycleStatus,
    HypothesisAssessmentStatus,
    SupportType,
)
from research_agent.domain.snapshot import InvestigationSnapshot


def has_counterevidence(claim: ClaimResponse) -> bool:
    return claim.status in {ClaimStatus.CONTESTED, ClaimStatus.CONTRADICTED} or any(
        link.support_type == SupportType.CONTRADICTING for link in claim.source_links
    )


def plan_cycle_objectives(
    snapshot: InvestigationSnapshot,
) -> tuple[list[str], list[CyclePlanningBasis]]:
    candidates: list[tuple[int, str, CyclePlanningBasis]] = []
    completed_objectives = {
        objective
        for cycle in snapshot.task.cycles
        if cycle.status == CycleStatus.COMPLETED
        for objective in cycle.objectives
        if objective not in cycle.unresolved_objectives
    }
    for cycle in snapshot.task.cycles:
        if cycle.status in {CycleStatus.BLOCKED, CycleStatus.FAILED}:
            for objective in cycle.unresolved_objectives or cycle.objectives:
                if objective.strip():
                    candidates.append(
                        (1, objective.strip(), CyclePlanningBasis(reason="incomplete_cycle"))
                    )
    addressed_claims = set()
    claims = {claim.id: claim for claim in snapshot.claims}
    for row in snapshot.hypotheses:
        hypothesis = row.hypothesis
        assessment = row.assessment
        if assessment is None:
            candidates.append(
                (
                    1,
                    f"Gather and map evidence to assess {hypothesis.label}: {hypothesis.statement}",
                    CyclePlanningBasis(reason="missing_assessment", hypothesis_id=hypothesis.id),
                )
            )
            continue
        linked_ids = sorted(
            {link.claim_id for link in assessment.evidence_links if link.claim_id in claims},
            key=str,
        )
        contradictory = (
            assessment.status == HypothesisAssessmentStatus.MIXED
            or any(link.relation == SupportType.CONTRADICTING for link in assessment.evidence_links)
            or any(has_counterevidence(claims[claim_id]) for claim_id in linked_ids)
        )
        if contradictory:
            candidates.append(
                (
                    0,
                    f"Review contradictory evidence and reassess {hypothesis.label}: "
                    f"{hypothesis.statement}",
                    CyclePlanningBasis(
                        reason="contradictory_evidence",
                        hypothesis_id=hypothesis.id,
                        assessment_id=assessment.id,
                        claim_ids=linked_ids,
                    ),
                )
            )
            addressed_claims.update(linked_ids)
        elif assessment.status == HypothesisAssessmentStatus.UNRESOLVED:
            candidates.append(
                (
                    2,
                    f"Identify evidence needed to resolve {hypothesis.label}: "
                    f"{hypothesis.statement}",
                    CyclePlanningBasis(
                        reason="unresolved_assessment",
                        hypothesis_id=hypothesis.id,
                        assessment_id=assessment.id,
                        claim_ids=linked_ids,
                    ),
                )
            )
            addressed_claims.update(linked_ids)

    for claim in snapshot.claims:
        if claim.id in addressed_claims:
            continue
        if has_counterevidence(claim):
            candidates.append(
                (
                    0,
                    f"Review the provenance and counterevidence for claim {claim.id}.",
                    CyclePlanningBasis(reason="contradictory_evidence", claim_ids=[claim.id]),
                )
            )
        elif claim.status in {ClaimStatus.UNVERIFIED, ClaimStatus.OBSOLETE, ClaimStatus.RETRACTED}:
            candidates.append(
                (
                    3,
                    f"Check whether claim {claim.id} is reliable enough to use in an assessment.",
                    CyclePlanningBasis(reason="unverified_claim", claim_ids=[claim.id]),
                )
            )

    analysed = {link.source_id for claim in snapshot.claims for link in claim.source_links}
    for source in snapshot.sources:
        if source.id not in analysed:
            candidates.append(
                (
                    4,
                    f"Analyze source {source.id} and extract provenance-backed claims.",
                    CyclePlanningBasis(reason="unanalysed_source", source_id=source.id),
                )
            )
    for question in snapshot.open_questions:
        if question.strip():
            candidates.append((5, question.strip(), CyclePlanningBasis(reason="open_question")))
    if not candidates and not snapshot.sources:
        candidates.append(
            (
                4,
                "Gather initial sources relevant to the investigation objective.",
                CyclePlanningBasis(reason="missing_evidence"),
            )
        )
    if not candidates:
        candidates.append(
            (
                6,
                "Review the stopping criteria and decide whether more evidence is needed.",
                CyclePlanningBasis(reason="review_stopping_criteria"),
            )
        )

    objectives: list[str] = []
    basis: list[CyclePlanningBasis] = []
    seen = set()
    # Stable sorting preserves brief and snapshot order within a priority.
    for _, objective, reason in sorted(candidates, key=lambda item: item[0]):
        if objective in completed_objectives:
            continue
        identity = (objective, reason.hypothesis_id, tuple(reason.claim_ids), reason.source_id)
        if identity in seen:
            continue
        seen.add(identity)
        objectives.append(objective)
        basis.append(reason)
        if len(objectives) == 3:
            break
    if not objectives:
        if not snapshot.sources:
            objectives.append("Gather initial sources relevant to the investigation objective.")
            basis.append(CyclePlanningBasis(reason="missing_evidence"))
        else:
            objectives.append(
                "Review the stopping criteria and decide whether more evidence is needed."
            )
            basis.append(CyclePlanningBasis(reason="review_stopping_criteria"))
    return objectives, basis
