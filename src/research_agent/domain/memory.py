"""Model-safe proposals; authority is supplied separately by application code."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from research_agent.domain.research import ClaimCreate, HypothesisAssessmentCreate


class MemoryOperation(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    ARCHIVE = "ARCHIVE"
    LOGICAL_DELETE = "LOGICAL_DELETE"
    RESTORE = "RESTORE"


class MemoryTarget(StrEnum):
    CLAIM = "claim"
    ASSESSMENT = "assessment"


class MemoryChangeProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    change_id: UUID = Field(default_factory=uuid4)
    target_type: MemoryTarget
    target_id: UUID
    operation: MemoryOperation
    expected_version: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=1000)
    claim: ClaimCreate | None = None
    assessment: HypothesisAssessmentCreate | None = None
    hypothesis_id: UUID | None = None

    @model_validator(mode="after")
    def shape(self) -> "MemoryChangeProposal":
        if not self.reason.strip():
            raise ValueError("Reason must not be blank")
        writes = self.operation in (MemoryOperation.CREATE, MemoryOperation.UPDATE)
        if self.target_type == MemoryTarget.CLAIM:
            if self.assessment is not None or self.hypothesis_id is not None:
                raise ValueError("Claim proposal cannot carry assessment fields")
            if writes != (self.claim is not None):
                raise ValueError("Claim data required only for CREATE/UPDATE")
        else:
            if self.claim is not None or writes != (self.assessment is not None):
                raise ValueError("Assessment data required only for CREATE/UPDATE")
            if (self.operation == MemoryOperation.CREATE) != (self.hypothesis_id is not None):
                raise ValueError("Hypothesis ID required only for assessment CREATE")
        if (self.operation == MemoryOperation.CREATE) != (self.expected_version == 0):
            raise ValueError("CREATE requires version zero; other operations require a version")
        return self


@dataclass(frozen=True)
class MemoryAuthority:
    """Trusted application context. Never deserialize this from a model/request body."""

    actor: Literal["local_operator", "claim_extractor", "model"]
    task_id: UUID
    can_commit: bool = False


class MemoryValidation(BaseModel):
    valid: bool
    reason: str


class AppliedMemoryChange(BaseModel):
    change_id: UUID
    task_id: UUID
    target_type: MemoryTarget
    target_id: UUID
    operation: str
    actor: str
    timestamp: datetime
    previous_version: int
    version: int
    previous_state: dict[str, Any] | None
    proposed_state: dict[str, Any]
    resulting_state: dict[str, Any]
    reason: str
    provenance: list[UUID]
    reverses_change_id: UUID | None = None


class MemoryHistory(BaseModel):
    """Reconstructable journal history for one governed target."""

    target_type: MemoryTarget
    target_id: UUID
    current_version: int
    changes: list[AppliedMemoryChange]


class HistoricalMemoryState(BaseModel):
    """The governed state reconstructed at a target version."""

    target_type: MemoryTarget
    target_id: UUID
    version: int
    state: dict[str, Any]
    change_id: UUID


class MemoryReversal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    change_id: UUID = Field(default_factory=uuid4)
    reason: str = Field(min_length=1, max_length=1000)


class MemoryConflict(Exception):
    """The target, version or dependent state conflicts with a requested change."""


class MemoryDenied(Exception):
    """The trusted caller lacks commit authority."""
