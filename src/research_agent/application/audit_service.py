"""Transactional audit events and bounded, task-scoped retrieval."""

from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from research_agent.application.research_service import ResearchTaskNotFound
from research_agent.domain.events import EventPayload, EventType, ResearchEventResponse
from research_agent.domain.research import utc_now
from research_agent.persistence.models import ResearchEventRecord, ResearchTaskRecord


class AuditService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def stage(self, task_id: UUID, event_type: EventType, payload: EventPayload) -> None:
        """Caller owns commit; successful writes and their events are atomic."""
        # Windows clock resolution can give several staged events the same time.
        # Writers hold the task row lock; preserve their order across transactions.
        latest = self.session.scalar(
            select(func.max(ResearchEventRecord.created_at)).where(
                ResearchEventRecord.task_id == task_id
            )
        )
        created_at = utc_now()
        previous = [
            record.created_at
            for record in self.session.new
            if isinstance(record, ResearchEventRecord) and record.task_id == task_id
        ]
        if latest is not None:
            previous.append(latest)
        if previous and created_at <= max(previous):
            created_at = max(previous) + timedelta(microseconds=1)
        self.session.add(
            ResearchEventRecord(
                id=uuid4(),
                task_id=task_id,
                event_type=event_type.value,
                payload=payload.model_dump(mode="json", exclude_none=True),
                created_at=created_at,
            )
        )

    def record_failure(self, task_id: UUID, event_type: EventType, payload: EventPayload) -> None:
        """Discard staged success events and persist the failure in a new transaction."""
        self.session.rollback()
        try:
            existing = self.session.scalar(
                select(ResearchTaskRecord.id)
                .where(ResearchTaskRecord.id == task_id)
                .with_for_update()
            )
            if existing is not None:
                self.stage(task_id, event_type, payload)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def list_events(self, task_id: UUID, limit: int, offset: int) -> list[ResearchEventResponse]:
        if self.session.get(ResearchTaskRecord, task_id) is None:
            raise ResearchTaskNotFound
        records = self.session.scalars(
            select(ResearchEventRecord)
            .where(ResearchEventRecord.task_id == task_id)
            .order_by(ResearchEventRecord.created_at, ResearchEventRecord.id)
            .limit(limit)
            .offset(offset)
        )
        return [
            ResearchEventResponse.model_validate(record, from_attributes=True) for record in records
        ]
