"""Allowlisted audit metadata; never source text, URLs, or exception messages."""

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from research_agent.domain.research import CycleStatus, TaskStatus
from research_agent.domain.security import SecurityState


class EventType(StrEnum):
    TASK_CREATED = "task.created"
    MEMORY_CHANGED = "memory.changed"
    MEMORY_REVERSED = "memory.reversed"
    TASK_STATUS_CHANGED = "task.status_changed"
    CYCLE_PLANNED = "cycle.planned"
    CYCLE_STARTED = "cycle.started"
    CYCLE_OUTCOME_RECORDED = "cycle.outcome_recorded"
    OBJECTIVE_REVIEWED = "cycle.objective_reviewed"
    CYCLE_PROGRESS_RECORDED = "cycle.progress_recorded"
    CYCLE_RECOVERED = "cycle.recovered"
    CYCLE_SECURITY_INTERRUPTED = "cycle.security_interrupted"
    SOURCE_CREATED = "source.created"
    SOURCE_REUSED = "source.reused"
    AGENT_OBSERVATION_RECORDED = "agent.observation_recorded"
    AGENT_OBSERVATION_FAILED = "agent.observation_failed"
    SOURCE_DEPENDENCE_CHANGED = "source.dependence_changed"
    STOPPING_DECISION_RECORDED = "task.stopping_decision_recorded"
    CLAIM_CREATED = "claim.created"
    CLAIM_REUSED = "claim.reused"
    EXTRACTION_COMPLETED = "extraction.completed"
    EXTRACTION_FAILED = "extraction.failed"
    RETRIEVAL_FAILED = "retrieval.failed"
    REPORT_DRAFT_GENERATED = "report.draft_generated"
    REPORT_DRAFT_FAILED = "report.draft_failed"
    REPORT_DRAFT_UNCERTAIN = "report.draft_uncertain"
    REPORT_DRAFT_RESERVED = "report.draft_reserved"
    REPORT_DRAFT_DISPATCHED = "report.draft_dispatched"
    REPORT_DRAFT_EXPIRED = "report.draft_expired"
    SECURITY_EVENT = "security.event"


class EventPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: UUID
    change_id: UUID | None = None
    target_id: UUID | None = None
    target_type: Literal["claim", "assessment"] | None = None
    actor: (
        Literal[
            "local_operator",
            "claim_extractor",
            "model",
            "agent_network",
            "source_runner",
            "agent_runner",
        ]
        | None
    ) = None
    attempt_id: UUID | None = None
    authority_epoch_id: UUID | None = None
    security_state_version: int | None = Field(default=None, ge=1)
    security_state: SecurityState | None = None
    from_attempt_status: Literal["RUNNING"] | None = None
    to_attempt_status: Literal["INTERRUPTED"] | None = None
    memory_operation: (
        Literal["CREATE", "UPDATE", "ARCHIVE", "LOGICAL_DELETE", "RESTORE", "REVERSE"] | None
    ) = None
    previous_version: int | None = None
    version: int | None = None
    from_status: TaskStatus | CycleStatus | None = None
    to_status: TaskStatus | CycleStatus | None = None
    cycle_number: int | None = None
    objective_index: int | None = None
    source_id: UUID | None = None
    claim_id: UUID | None = None
    relationship_id: UUID | None = None
    related_source_id: UUID | None = None
    dependence_kind: Literal["derived_from", "common_origin"] | None = None
    dependence_direction: Literal["low_to_high", "high_to_low", "none"] | None = None
    relationship_lifecycle: Literal["active", "retracted"] | None = None
    relationship_revision: int | None = Field(default=None, ge=1)
    stopping_decision_id: UUID | None = None
    stopping_reason: Literal[
        "evidence_sufficient",
        "resource_limited",
        "evidence_unavailable",
        "operator_stopped",
    ] | None = None
    stopping_revision: int | None = Field(default=None, ge=1)
    evidence_fingerprint: str | None = None
    claim_count: int | None = None
    unresolved_count: int | None = None
    provider: str | None = None
    model: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    previous_state_digest: str | None = None
    new_state_digest: str | None = None
    provenance: list[UUID] | None = None
    result: Literal["accepted", "reused", "rejected", "committed", "failed"] | None = None
    change_reason: (
        Literal[
            "operator_memory_change",
            "operator_memory_reversal",
            "unauthorized_memory_mutation",
        ]
        | None
    ) = None
    reason: (
        Literal[
            "security_policy_interrupted",
            "extraction_failed",
            "retrieval_rejected",
            "domain_not_enabled",
            "report_generation_failed",
            "report_input_too_large",
            "report_budget_exceeded",
            "provider_outcome_unknown",
            "provider_dispatch_authority_revoked",
            "reservation_expired",
            "agent_network_failed",
        ]
        | None
    ) = None


class ResearchEventResponse(BaseModel):
    id: UUID
    task_id: UUID
    event_type: str
    payload: EventPayload
    created_at: datetime
