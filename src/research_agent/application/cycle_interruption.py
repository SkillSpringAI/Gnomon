"""Exact-attempt containment bookkeeping; no general outcome or memory authority."""

from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_agent.application.audit_service import AuditService
from research_agent.application.research_service import TaskStateConflict
from research_agent.application.security_capability import (
    AuthorityDirection,
    SecurityCapability,
    require_locked_capability,
)
from research_agent.domain.events import EventPayload, EventType
from research_agent.domain.research import CycleStatus, ResearchTask, utc_now
from research_agent.persistence.models import (
    ResearchCycleAttemptRecord,
    ResearchCycleRecord,
    ResearchEventRecord,
    ResearchTaskRecord,
)
from research_agent.persistence.repositories import SqlAlchemyResearchTaskRepository


class CycleRunnerIdentity(StrEnum):
    """Trusted application call sites; never derived from external request content."""

    SOURCE = "source_runner"
    AGENT = "agent_runner"


class CycleInterruptionService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def close(
        self,
        task_id: UUID,
        cycle_number: int,
        attempt_id: UUID,
        *,
        caller: CycleRunnerIdentity,
    ) -> ResearchTask:
        # Discard pending research work; closure always owns a new transaction.
        self.session.rollback()
        try:
            if not isinstance(caller, CycleRunnerIdentity):
                raise TaskStateConflict("Untrusted interruption caller")
            task = self.session.scalar(
                select(ResearchTaskRecord)
                .where(ResearchTaskRecord.id == task_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if task is None:
                raise TaskStateConflict("Interruption task is unavailable")
            authority = require_locked_capability(
                self.session,
                SecurityCapability.SECURITY_CONTAINMENT,
                AuthorityDirection.REDUCE,
            )
            cycle = self.session.scalar(
                select(ResearchCycleRecord)
                .where(
                    ResearchCycleRecord.task_id == task_id,
                    ResearchCycleRecord.cycle_number == cycle_number,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            attempt = self.session.scalar(
                select(ResearchCycleAttemptRecord)
                .where(ResearchCycleAttemptRecord.id == attempt_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if (
                cycle is None
                or attempt is None
                or attempt.task_id != task_id
                or attempt.cycle_id != cycle.id
            ):
                raise TaskStateConflict("Interruption attempt does not match cycle")
            prior = self.session.scalar(
                select(ResearchEventRecord).where(
                    ResearchEventRecord.task_id == task_id,
                    ResearchEventRecord.event_type == EventType.CYCLE_SECURITY_INTERRUPTED.value,
                    ResearchEventRecord.payload["attempt_id"].astext == str(attempt_id),
                )
            )
            if prior is not None:
                if (
                    prior.payload.get("actor") != caller.value
                    or prior.payload.get("cycle_number") != cycle_number
                    or prior.payload.get("reason") != "security_policy_interrupted"
                    or cycle.status != "blocked"
                    or cycle.recovery_reason != "security_policy_interrupted"
                    or attempt.status != "INTERRUPTED"
                    or attempt.stage != "INTERRUPTED"
                    or attempt.recovery_reason != "security_policy_interrupted"
                ):
                    raise TaskStateConflict("Interruption conflicts with recorded closure")
            else:
                running = self.session.scalars(
                    select(ResearchCycleAttemptRecord.id).where(
                        ResearchCycleAttemptRecord.cycle_id == cycle.id,
                        ResearchCycleAttemptRecord.status == "RUNNING",
                    )
                ).all()
                if (
                    cycle.status != "active"
                    or attempt.status != "RUNNING"
                    or running != [attempt_id]
                ):
                    raise TaskStateConflict("Interruption requires one exact running attempt")
                now = utc_now()
                cycle.status = "blocked"
                cycle.completed_at = now
                cycle.result_summary = (
                    "Security policy interrupted this cycle; committed progress retained."
                )
                cycle.recovery_reason = "security_policy_interrupted"
                attempt.status = "INTERRUPTED"
                attempt.stage = "INTERRUPTED"
                attempt.finished_at = now
                attempt.recovery_reason = "security_policy_interrupted"
                task.updated_at = now
                AuditService(self.session).stage(
                    task_id,
                    EventType.CYCLE_SECURITY_INTERRUPTED,
                    EventPayload(
                        operation_id=uuid4(),
                        attempt_id=attempt_id,
                        cycle_number=cycle_number,
                        actor=caller.value,
                        reason="security_policy_interrupted",
                        from_status=CycleStatus.ACTIVE,
                        to_status=CycleStatus.BLOCKED,
                        from_attempt_status="RUNNING",
                        to_attempt_status="INTERRUPTED",
                        authority_epoch_id=authority.authority_epoch_id.value,
                        security_state_version=authority.version,
                        security_state=authority.state,
                        result="committed",
                    ),
                )
            self.session.flush()
            result = SqlAlchemyResearchTaskRepository(self.session).get(task_id, for_update=True)
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise
