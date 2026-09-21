"""Deterministic report-draft provider for local development and tests."""

from research_agent.domain.report import InvestigationReport, ReportDraft
from research_agent.domain.research import HypothesisAssessmentStatus, utc_now


class RuleBasedReportDraftGenerator:
    """Format structured evidence without inferring unsupported conclusions."""

    provider = "rule_based"
    model = "local-development"

    def generate(self, report: InvestigationReport) -> ReportDraft:
        lines = [
            f"# {report.title}",
            "",
            f"Objective: {report.objective}",
            "",
            "## Evidence inventory",
            report.summary,
        ]
        if report.hypotheses:
            lines.extend(["", "## Hypotheses"])
            for hypothesis in report.hypotheses:
                status = (
                    hypothesis.assessment_status.value
                    if hypothesis.assessment_status
                    else "not assessed"
                )
                lines.append(f"- {hypothesis.label}: {status} (ID: {hypothesis.id})")
                if hypothesis.assessment_status == HypothesisAssessmentStatus.UNRESOLVED:
                    lines.append("  - Assessment remains unresolved.")
        if report.claims:
            lines.extend(["", "## Claims and provenance"])
            for claim in report.claims:
                source_ids = ", ".join(str(link.source_id) for link in claim.source_links)
                lines.append(
                    f"- [{claim.status.value}; confidence {claim.confidence:.2f}] "
                    f"{claim.statement} (Claim ID: {claim.id}; Sources: {source_ids})"
                )
        if report.source_dependence:
            dependence = report.source_dependence
            lines.extend(["", "## Source dependence"])
            lines.append(
                f"Observed {len(dependence.examined_relationships)} declared relationship(s); "
                f"{len(dependence.visited_source_ids)} source(s) were visited."
            )
            lines.append(
                "Missing or partial dependence data remains unknown and does not establish "
                "independence."
            )
            if dependence.truncated:
                lines.append(
                    f"Projection truncated at {dependence.overflow_reason}; "
                    "review the bounded result before relying on source counts."
                )
        if report.cycles:
            lines.extend(["", "## Cycle history"])
            for cycle in report.cycles:
                lines.append(
                    f"- Cycle {cycle.number}: {cycle.status.value}; "
                    f"{len(cycle.objectives)} objective(s), "
                    f"{len(cycle.evidence_ids)} evidence record(s), "
                    f"{len(cycle.claim_ids)} claim record(s)."
                )
        if report.open_questions or report.unresolved_objectives:
            lines.extend(["", "## Open work"])
            for question in report.open_questions:
                lines.append(f"- Question: {question}")
            for objective in report.unresolved_objectives:
                lines.append(f"- Unresolved objective: {objective}")
        if report.limitations:
            lines.extend(["", "## Limitations"])
            lines.extend(f"- {limitation}" for limitation in report.limitations)
        lines.extend(
            [
                "",
                "This is a structured evidence draft. It does not establish conclusions "
                "beyond the stored claims and assessments.",
            ]
        )
        return ReportDraft(
            task_id=report.task_id,
            provider=self.provider,
            model=self.model,
            generated_at=utc_now(),
            content="\n".join(lines),
            cited_source_ids=[source.id for source in report.sources],
            cited_claim_ids=[claim.id for claim in report.claims],
            limitations=report.limitations,
        )
