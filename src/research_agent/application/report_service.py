"""Deterministic report assembly from a consistent investigation snapshot."""

from collections.abc import Iterable

from research_agent.application.agent_comparison_service import AgentComparisonService
from research_agent.application.agent_observation_projection import agent_observations
from research_agent.application.cycle_planner import (
    review_evidence_fingerprint,
    review_is_current,
    reviewed_complete,
)
from research_agent.domain.report import (
    InvestigationReport,
    ReportCycle,
    ReportHypothesis,
    ReportSource,
    ReportStoppingDecision,
)
from research_agent.domain.research import CycleStatus, StoppingDecision, recovery_fingerprint
from research_agent.domain.snapshot import InvestigationSnapshot


class ReportService:
    """Build an evidence inventory without generating unsupported conclusions."""

    def build(
        self,
        snapshot: InvestigationSnapshot,
        *,
        stopping_decision: StoppingDecision | None = None,
        stopping_decision_stale: bool = False,
    ) -> InvestigationReport:
        assessments = {row.hypothesis.id: row.assessment for row in snapshot.hypotheses}
        hypotheses = []
        for row in snapshot.hypotheses:
            assessment = assessments[row.hypothesis.id]
            hypotheses.append(
                ReportHypothesis(
                    id=row.hypothesis.id,
                    label=row.hypothesis.label,
                    statement=row.hypothesis.statement,
                    assessment_status=assessment.status if assessment else None,
                    assessment_summary=assessment.summary if assessment else None,
                    confidence=assessment.confidence if assessment else None,
                    claim_ids=[link.claim_id for link in assessment.evidence_links]
                    if assessment
                    else [],
                )
            )

        cycles = [
            ReportCycle(
                number=cycle.number,
                status=cycle.status,
                started_at=cycle.started_at,
                progress_tracked=cycle.progress_tracked,
                recovery_fingerprint=recovery_fingerprint(snapshot.task.status, cycle)
                if cycle.status == CycleStatus.ACTIVE
                else None,
                objectives=cycle.objectives,
                result_summary=cycle.result_summary,
                unresolved_objectives=cycle.unresolved_objectives,
                evidence_ids=cycle.evidence_ids,
                claim_ids=cycle.claim_ids,
                attempted_objectives=cycle.attempted_objectives,
                objective_results=cycle.objective_results,
                objective_reviews=cycle.objective_reviews,
                stale_review_ids=[
                    item.id
                    for item in cycle.objective_reviews
                    if not review_is_current(item, snapshot)
                ],
            )
            for cycle in snapshot.task.cycles
        ]
        unresolved_objectives = _unique(
            objective
            for cycle in snapshot.task.cycles
            for objective in cycle.unresolved_objectives
            if not reviewed_complete(objective, snapshot)
        )
        unresolved_objectives = _unique(
            unresolved_objectives
            + [
                review.objective
                for cycle in snapshot.task.cycles
                for review in cycle.objective_reviews
                if not reviewed_complete(review.objective, snapshot)
            ]
        )
        open_questions = _unique(snapshot.open_questions)
        limitations: list[str] = []
        observations = agent_observations(snapshot)
        agent_comparison = AgentComparisonService().compare(observations)
        if not snapshot.sources:
            limitations.append("No source evidence has been stored for this investigation.")
        if not snapshot.claims:
            limitations.append("No structured claims have been extracted from the evidence.")
        if any(row.assessment is None for row in snapshot.hypotheses):
            limitations.append("One or more hypotheses have no current assessment.")
        if any(
            claim.status.value in {"unverified", "contested", "contradicted"}
            for claim in snapshot.claims
        ):
            limitations.append("Some claims remain unverified or contested.")
        if agent_comparison.comparisons:
            limitations.append(
                "Agent observation comparisons are untrusted context and do not establish truth."
            )
        if agent_comparison.omitted_observation_count:
            limitations.append(
                f"Agent comparisons omit {agent_comparison.omitted_observation_count} older "
                "observations; absence of a reported contradiction is not exhaustive."
            )
        dependence = snapshot.source_dependence
        if snapshot.sources:
            limitations.append(
                "Source dependence is only partially known; absent relationships do not "
                "establish independent evidence."
            )
            if dependence and dependence.truncated:
                limitations.append(
                    "The source-dependence view is bounded and incomplete; review its "
                    "overflow limitation before relying on source counts."
                )
            if dependence and dependence.invalid:
                limitations.append(
                    "Invalid directed source-dependence data was detected; do not rely on "
                    "this graph as a valid corroboration structure."
                )
        summary = (
            f"Evidence inventory for {snapshot.task.brief.title}: "
            f"{len(snapshot.sources)} sources, {len(snapshot.claims)} claims, "
            f"{sum(row.assessment is not None for row in snapshot.hypotheses)} assessed hypotheses."
        )
        return InvestigationReport(
            task_id=snapshot.task.id,
            review_evidence_fingerprint=review_evidence_fingerprint(snapshot),
            title=snapshot.task.brief.title,
            objective=snapshot.task.brief.objective,
            task_status=snapshot.task.status,
            summary=summary,
            hypotheses=hypotheses,
            claims=snapshot.claims,
            sources=[
                ReportSource(
                    id=source.id,
                    source_type=source.source_type,
                    title=source.title,
                    uri=source.uri,
                    publisher=source.publisher,
                    observed_at=source.observed_at,
                )
                for source in snapshot.sources
            ],
            cycles=cycles,
            open_questions=open_questions,
            unresolved_objectives=unresolved_objectives,
            limitations=limitations,
            agent_comparison=agent_comparison if observations else None,
            source_dependence=dependence,
            stopping_decision=(
                ReportStoppingDecision(
                    decision_id=stopping_decision.decision_id,
                    reason=stopping_decision.reason.value,
                    rationale=stopping_decision.rationale,
                    evidence_fingerprint=stopping_decision.evidence_fingerprint,
                    stale=stopping_decision_stale,
                    limitations=stopping_decision.limitations,
                )
                if stopping_decision is not None
                else ReportStoppingDecision(
                    reason="unspecified",
                    limitations=[
                        "This investigation was concluded without a persisted stopping decision."
                    ],
                )
            ),
        )


def _unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result
