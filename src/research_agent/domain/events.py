"""Allowlisted audit metadata; never source text, URLs, or exception messages."""

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from research_agent.domain.research import CycleStatus, TaskStatus


class EventType(StrEnum):
    TASK_STATUS_CHANGED = "task.status_changed"
    CYCLE_PLANNED = "cycle.planned"
    CYCLE_STARTED = "cycle.started"
    CYCLE_OUTCOME_RECORDED = "cycle.outcome_recorded"
    SOURCE_CREATED = "source.created"
    SOURCE_REUSED = "source.reused"
    CLAIM_CREATED = "claim.created"
    CLAIM_REUSED = "claim.reused"
    EXTRACTION_COMPLETED = "extraction.completed"
    EXTRACTION_FAILED = "extraction.failed"
    RETRIEVAL_FAILED = "retrieval.failed"
    REPORT_DRAFT_GENERATED = "report.draft_generated"
    REPORT_DRAFT_FAILED = "report.draft_failed"


class EventPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: UUID
    from_status: TaskStatus | CycleStatus | None = None
    to_status: TaskStatus | CycleStatus | None = None
    cycle_number: int | None = None
    source_id: UUID | None = None
    claim_id: UUID | None = None
    claim_count: int | None = None
    unresolved_count: int | None = None
    provider: str | None = None
    model: str | None = None
    reason: Literal[
        "extraction_failed",
        "retrieval_rejected",
        "domain_not_enabled",
        "report_generation_failed",
        "report_budget_exceeded",
    ] | None = None


class ResearchEventResponse(BaseModel):
    id: UUID
    task_id: UUID
    event_type: str
    payload: EventPayload
    created_at: datetime
