"""Read-only projection of durable cycle-attempt progress."""

from typing import Literal, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_agent.domain.research import CycleAttemptProgress, CycleStatus
from research_agent.persistence.models import (
    ResearchCycleAttemptRecord,
    ResearchCycleRecord,
)


class CycleAttemptNotFound(LookupError):
    """No persisted attempt exists for the requested task-scoped cycle."""


AttemptStatus = Literal[
    "RUNNING",
    "COMPLETED",
    "BLOCKED",
    "FAILED",
    "INTERRUPTED",
]

DurableStage = Literal[
    "CREATED",
    "STARTED",
    "QUESTIONING",
    "EVIDENCE_RECORDED",
    "EXTRACTING_CLAIMS",
    "FINALIZING",
    "COMPLETED",
    "BLOCKED",
    "FAILED",
    "INTERRUPTED",
]


def _attempt_status(value: str) -> AttemptStatus:
    allowed = {
        "RUNNING",
        "COMPLETED",
        "BLOCKED",
        "FAILED",
        "INTERRUPTED",
    }
    if value not in allowed:
        raise ValueError(f"Unknown attempt status: {value}")
    return cast(AttemptStatus, value)


def _durable_stage(value: str) -> DurableStage:
    allowed = {
        "CREATED",
        "STARTED",
        "QUESTIONING",
        "EVIDENCE_RECORDED",
        "EXTRACTING_CLAIMS",
        "FINALIZING",
        "COMPLETED",
        "BLOCKED",
        "FAILED",
        "INTERRUPTED",
    }
    if value not in allowed:
        raise ValueError(f"Unknown durable stage: {value}")
    return cast(DurableStage, value)


class CycleAttemptProgressService:
    """Project one attempt and its cycle state without mutation or recovery."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def latest(self, task_id: UUID, cycle_number: int) -> CycleAttemptProgress:
        row = self.session.execute(
            select(ResearchCycleAttemptRecord, ResearchCycleRecord)
            .join(
                ResearchCycleRecord,
                ResearchCycleAttemptRecord.cycle_id == ResearchCycleRecord.id,
            )
            .where(
                ResearchCycleAttemptRecord.task_id == task_id,
                ResearchCycleRecord.task_id == task_id,
                ResearchCycleRecord.cycle_number == cycle_number,
            )
            .order_by(
                ResearchCycleAttemptRecord.started_at.desc(),
                ResearchCycleAttemptRecord.id.desc(),
            )
            .limit(1)
        ).one_or_none()
        if row is None:
            raise CycleAttemptNotFound
        attempt, cycle = row
        cycle_status = CycleStatus(cycle.status)
        return CycleAttemptProgress(
            attempt_id=attempt.id,
            cycle_number=cycle.cycle_number,
            attempt_status=_attempt_status(attempt.status),
            last_durable_stage=_durable_stage(attempt.stage),
            started_at=attempt.started_at,
            finished_at=attempt.finished_at,
            recovery_reason=attempt.recovery_reason,
            retained_evidence_ids=[UUID(item) for item in attempt.evidence_ids],
            retained_claim_ids=[UUID(item) for item in attempt.claim_ids],
            attempted_objectives=list(cycle.attempted_objectives),
            unresolved_objectives=list(cycle.unresolved_objectives),
            cycle_status=cycle_status,
            cycle_active=cycle_status is CycleStatus.ACTIVE,
        )
