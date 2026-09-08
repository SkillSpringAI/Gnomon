"""Allowlisted audit metadata; never source text, URLs, or exception messages."""

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from research_agent.domain.research import TaskStatus


class EventType(StrEnum):
    TASK_STATUS_CHANGED = "task.status_changed"
    CYCLE_PLANNED = "cycle.planned"
    SOURCE_CREATED = "source.created"
    SOURCE_REUSED = "source.reused"
    CLAIM_CREATED = "claim.created"
    CLAIM_REUSED = "claim.reused"
    EXTRACTION_COMPLETED = "extraction.completed"
    EXTRACTION_FAILED = "extraction.failed"
    RETRIEVAL_FAILED = "retrieval.failed"


class EventPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: UUID
    from_status: TaskStatus | None = None
    to_status: TaskStatus | None = None
    cycle_number: int | None = None
    source_id: UUID | None = None
    claim_id: UUID | None = None
    claim_count: int | None = None
    reason: Literal["extraction_failed", "retrieval_rejected", "domain_not_enabled"] | None = None


class ResearchEventResponse(BaseModel):
    id: UUID
    task_id: UUID
    event_type: str
    payload: EventPayload
    created_at: datetime
