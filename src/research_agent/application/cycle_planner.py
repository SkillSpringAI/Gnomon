"""Deterministic, evidence-aware planning. No text inference or tool execution."""

import json
from hashlib import sha256

from research_agent.application.agent_comparison_service import AgentComparisonService
from research_agent.application.agent_observation_projection import agent_observations
from research_agent.domain.research import (
    ClaimResponse,
    ClaimStatus,
    CyclePlanningBasis,
    CycleStatus,
    HypothesisAssessmentStatus,
    SupportType,
)
from research_agent.domain.snapshot import InvestigationSnapshot


def _identity(objective: str, basis: CyclePlanningBasis) -> tuple[str, str]:
    payload = basis.model_dump(mode="json")
    payload["claim_ids"] = sorted(set(payload["claim_ids"]))
    payload["source_ids"] = sorted(set(payload["source_ids"]))
    return objective.strip(), json.dumps(payload, sort_keys=True)


def _with_evidence(
    basis: CyclePlanningBasis, snapshot: InvestigationSnapshot,
) -> CyclePlanningBasis:
    """Persist a digest of the relevant evidence state, not the raw evidence."""
    if basis.evidence_fingerprint is not None:
        return basis
    claim_ids = set(basis.claim_ids)
    source_ids = set(basis.source_ids)
    if basis.source_id is not None:
        source_ids.add(basis.source_id)
    broad = basis.reason in {
        "missing_assessment", "missing_evidence", "open_question", "incomplete_cycle",
        "review_stopping_criteria", "agent_comparison_limit",
    }
    claims = [item for item in snapshot.claims if broad or item.id in claim_ids]
    source_ids.update(link.source_id for claim in claims for link in claim.source_links)
    sources = [item for item in snapshot.sources if broad or item.id in source_ids]
    hypotheses = [
        item for item in snapshot.hypotheses
        if broad or item.hypothesis.id == basis.hypothesis_id
    ]
    payload = {
        "claims": [
            item.model_dump(mode="json") for item in sorted(claims, key=lambda c: str(c.id))
        ],
        "sources": [
            item.model_dump(mode="json") for item in sorted(sources, key=lambda s: str(s.id))
        ],
        "hypotheses": [item.model_dump(mode="json") for item in sorted(
            hypotheses, key=lambda h: str(h.hypothesis.id)
        )],
    }
    digest = sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return basis.model_copy(update={"evidence_fingerprint": digest})


def has_counterevidence(claim: ClaimResponse) -> bool:
    return claim.status in {ClaimStatus.CONTESTED, ClaimStatus.CONTRADICTED} or any(
        link.support_type == SupportType.CONTRADICTING for link in claim.source_links
    )


def plan_cycle_objectives(
    snapshot: InvestigationSnapshot,
) -> tuple[list[str], list[CyclePlanningBasis]]:
    candidates: list[tuple[int, str, CyclePlanningBasis]] = []
    completed: set[tuple[str, str]] = set()
    outstanding: dict[str, CyclePlanningBasis] = {}
    for cycle in sorted(snapshot.task.cycles, key=lambda item: item.number):
        if cycle.status not in {CycleStatus.COMPLETED, CycleStatus.BLOCKED, CycleStatus.FAILED}:
            continue
        unresolved = {item.strip() for item in cycle.unresolved_objectives}
        if cycle.status != CycleStatus.COMPLETED and not unresolved:
            unresolved = {item.strip() for item in cycle.objectives}
        for index, raw_objective in enumerate(cycle.objectives):
            objective = raw_objective.strip()
            reason = (
                cycle.planning_basis[index] if index < len(cycle.planning_basis)
                else CyclePlanningBasis(reason="incomplete_cycle")
            )
            identity = _identity(objective, reason)
            if objective in unresolved:
                completed.discard(identity)
                outstanding[objective] = reason
            elif cycle.status == CycleStatus.COMPLETED:
                completed.add(identity)
                outstanding.pop(objective, None)
        for objective in unresolved:
            if objective and objective not in {item.strip() for item in cycle.objectives}:
                outstanding[objective] = CyclePlanningBasis(reason="incomplete_cycle")
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
    observations = agent_observations(snapshot)
    comparison = AgentComparisonService().compare(observations)
    contradictions = [
        item for item in comparison.comparisons if item.relation.value == "contradiction"
    ]
    if contradictions:
        source_ids = sorted(
            {source_id for item in contradictions for source_id in (item.left_id, item.right_id)},
            key=str,
        )
        candidates.append(
            (
                0,
                "Compare contradictory agent observations and seek independent corroboration.",
                CyclePlanningBasis(reason="agent_contradiction", source_ids=source_ids),
            )
        )
    elif observations and comparison.distinct_agent_count < 2:
        source_ids = comparison.observation_ids
        candidates.append(
            (
                2,
                "Seek another agent perspective and verify the independence of its evidence.",
                CyclePlanningBasis(reason="agent_corroboration", source_ids=source_ids),
            )
        )
    if comparison.omitted_observation_count:
        candidates.append(
            (
                1,
                "Review older agent observations omitted from the bounded comparison.",
                CyclePlanningBasis(reason="agent_comparison_limit"),
            )
        )
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

    current_objectives = {objective for _, objective, _ in candidates}
    for objective, reason in outstanding.items():
        if objective and objective not in current_objectives:
            candidates.append((1, objective, reason))

    objectives: list[str] = []
    basis: list[CyclePlanningBasis] = []
    seen = set()
    # Stable sorting preserves brief and snapshot order within a priority.
    for _, objective, reason in sorted(
        candidates, key=lambda item: min(item[0], 1) if item[1] in outstanding else item[0]
    ):
        reason = _with_evidence(reason, snapshot)
        identity = _identity(objective, reason)
        if identity in completed or identity in seen:
            continue
        seen.add(identity)
        objectives.append(objective)
        basis.append(reason)
        if len(objectives) == 3:
            break
    if not objectives:
        objectives.append(
            "Review the stopping criteria and decide whether more evidence is needed."
        )
        basis.append(CyclePlanningBasis(reason="review_stopping_criteria"))
    return objectives, [_with_evidence(reason, snapshot) for reason in basis]
