"""Deterministic comparison read models for untrusted agent observations."""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ObservationRelation(StrEnum):
    AGREEMENT = "agreement"
    CONTRADICTION = "contradiction"
    DUPLICATE = "duplicate"
    UNRELATED = "unrelated"


class ObservationComparison(BaseModel):
    """A comparison result, not a truth judgment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    left_id: UUID
    right_id: UUID
    relation: ObservationRelation


class AgentObservationComparison(BaseModel):
    """Bounded summary of how a set of agent observations relate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_ids: list[UUID] = Field(max_length=100)
    comparisons: list[ObservationComparison] = Field(max_length=4950)
    distinct_agent_count: int = Field(ge=0, le=100)
    omitted_observation_count: int = Field(default=0, ge=0)
    note: str = (
        "Comparisons describe response relationships; they do not establish truth. "
        "Distinct identities do not establish independent evidence. Counts describe the "
        "selected observations; at most the latest 100 are compared."
    )
