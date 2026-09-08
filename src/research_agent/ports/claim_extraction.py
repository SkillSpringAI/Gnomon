"""Interfaces for extracting structured claims from source evidence."""

from typing import Protocol

from research_agent.domain.research import ClaimCreate, SourceResponse


class ClaimExtractor(Protocol):
    """Extract conservative claim proposals from one stored source."""

    def extract(self, source: SourceResponse) -> list[ClaimCreate]:
        """Return provenance-linked, unverified claim proposals."""
