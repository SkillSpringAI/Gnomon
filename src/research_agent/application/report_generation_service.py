"""Application service for provider-backed report draft generation."""

from research_agent.domain.report import InvestigationReport, ReportDraft
from research_agent.ports.reporting import ReportDraftGenerator


class ReportGenerationError(Exception):
    """Provider output was unavailable or failed the report contract."""


class ReportGenerationService:
    """Keep provider execution separate from snapshot assembly and persistence."""

    def __init__(self, generator: ReportDraftGenerator) -> None:
        self.generator = generator

    def generate(self, report: InvestigationReport) -> ReportDraft:
        try:
            draft = ReportDraft.model_validate(self.generator.generate(report))
        except Exception as exc:
            raise ReportGenerationError from exc
        if draft.task_id != report.task_id:
            raise ReportGenerationError
        if not set(draft.cited_source_ids).issubset({source.id for source in report.sources}):
            raise ReportGenerationError
        if not set(draft.cited_claim_ids).issubset({claim.id for claim in report.claims}):
            raise ReportGenerationError
        if any(
            token in draft.content.lower()
            for token in ("api_key=", "api-key=", "password=", "secret=")
        ):
            raise ReportGenerationError
        return draft
