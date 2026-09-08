"""Interfaces for retrieving external source material."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from research_agent.domain.research import SourceType


class SourceTarget(BaseModel):
    """Approved target for source retrieval."""

    model_config = ConfigDict(extra="forbid")

    uri: str = Field(min_length=1, max_length=2000)
    source_type: SourceType = SourceType.WEB_PAGE


class RetrievedSource(BaseModel):
    """Normalized result from a retrieval adapter."""

    model_config = ConfigDict(extra="forbid")

    uri: str
    title: str
    content: str
    content_type: str
    publisher: str | None = None


class SourceRetriever(Protocol):
    """Retrieve one approved source."""

    def fetch(self, target: SourceTarget) -> RetrievedSource:
        """Fetch and normalize source content."""
