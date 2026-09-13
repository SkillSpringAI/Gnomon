"""Platform-neutral, untrusted agent-network domain objects."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class AgentCapability(StrEnum):
    SOURCE_FINDER = "source_finder"
    DOMAIN_SPECIALIST = "domain_specialist"
    CRITIC = "critic"
    CASE_STUDY = "case_study"


class ObservationStance(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    UNKNOWN = "unknown"


class AgentIdentity(BaseModel):
    """An observed identity; identity does not imply trust or authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid4)
    network: str = Field(min_length=1, max_length=100)
    platform_agent_id: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    capabilities: list[AgentCapability] = Field(default_factory=list, max_length=10)


class AgentQuestion(BaseModel):
    """A bounded research question sent to an external agent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    question: str = Field(min_length=1, max_length=4000)
    agent_id: UUID
    created_at: datetime = Field(default_factory=utc_now)


class AgentObservation(BaseModel):
    """Untrusted agent output, retained as an observation rather than a claim."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid4)
    question_id: UUID
    agent: AgentIdentity
    content: str = Field(min_length=1, max_length=20_000)
    observed_at: datetime = Field(default_factory=utc_now)
    scenario: str = Field(min_length=1, max_length=40)
    stance: ObservationStance = ObservationStance.UNKNOWN
    duplicate_of: UUID | None = None
