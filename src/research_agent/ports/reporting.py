"""Provider boundary for generated report prose."""

from typing import Protocol

from research_agent.domain.report import InvestigationReport, ReportDraft


class ReportDraftGenerator(Protocol):
    """Generate prose from a validated, provenance-preserving report model."""

    def generate(self, report: InvestigationReport) -> ReportDraft:
        """Return a draft without changing persisted investigation state."""
