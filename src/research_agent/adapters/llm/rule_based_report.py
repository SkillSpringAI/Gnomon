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
