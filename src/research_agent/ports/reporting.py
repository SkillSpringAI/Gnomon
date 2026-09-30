"""Provider boundary for generated report prose."""

from typing import Protocol

from research_agent.domain.report import InvestigationReport, ReportDraft


class ProviderRequestRejected(Exception):
    """The provider definitively rejected this invocation without a usable result."""


class ReportDraftGenerator(Protocol):
    """Generate prose from a validated, provenance-preserving report model."""

    def generate(self, report: InvestigationReport) -> ReportDraft:
        """Return a draft without changing persisted investigation state."""
