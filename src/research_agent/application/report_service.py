"""Deterministic report assembly from a consistent investigation snapshot."""

from collections.abc import Iterable

from research_agent.domain.report import (
    InvestigationReport,
    ReportCycle,
    ReportHypothesis,
    ReportSource,
)
from research_agent.domain.snapshot import InvestigationSnapshot


class ReportService:
    """Build an evidence inventory without generating unsupported conclusions."""

    def build(self, snapshot: InvestigationSnapshot) -> InvestigationReport:
        assessments = {
            row.hypothesis.id: row.assessment for row in snapshot.hypotheses
        }
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
                objectives=cycle.objectives,
                result_summary=cycle.result_summary,
                unresolved_objectives=cycle.unresolved_objectives,
                evidence_ids=cycle.evidence_ids,
                claim_ids=cycle.claim_ids,
            )
            for cycle in snapshot.task.cycles
        ]
        unresolved_objectives = _unique(
            objective
            for cycle in snapshot.task.cycles
            for objective in cycle.unresolved_objectives
        )
        open_questions = _unique(snapshot.open_questions)
        limitations: list[str] = []
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
        summary = (
            f"Evidence inventory for {snapshot.task.brief.title}: "
            f"{len(snapshot.sources)} sources, {len(snapshot.claims)} claims, "
            f"{sum(row.assessment is not None for row in snapshot.hypotheses)} assessed hypotheses."
        )
        return InvestigationReport(
            task_id=snapshot.task.id,
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
