"""Atomic provider-budget reservations for externally generated report drafts."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from research_agent.persistence.models import ReportGenerationAttemptRecord, ResearchTaskRecord


class ProviderBudgetExceeded(Exception):
    """No reservation capacity remains for this investigation."""


class ProviderAttemptConflict(Exception):
    """An idempotency key was already used for another investigation."""


class ProviderBudgetService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def reserve(
        self, task_id: UUID, operation_id: UUID, limit: int, timeout_seconds: int
    ) -> ReportGenerationAttemptRecord:
        task = self.session.scalar(
            select(ResearchTaskRecord)
            .where(ResearchTaskRecord.id == task_id)
            .with_for_update()
        )
        if task is None:
            raise LookupError("Investigation not found")
        existing = self.session.get(ReportGenerationAttemptRecord, operation_id)
        if existing is not None:
            if existing.task_id != task_id:
                raise ProviderAttemptConflict("Operation ID belongs to another investigation")
            raise ProviderAttemptConflict("Operation ID has already been used")
        now = datetime.now(UTC)
        expired = self.session.scalars(
            select(ReportGenerationAttemptRecord).where(
                ReportGenerationAttemptRecord.task_id == task_id,
                ReportGenerationAttemptRecord.status == "PENDING",
                ReportGenerationAttemptRecord.expires_at <= now,
            )
        ).all()
        for attempt in expired:
            attempt.status = "EXPIRED"
            attempt.finished_at = now
            attempt.error_reason = "reservation_expired"
        self.session.flush()
        used = self.session.scalar(
            select(func.count(ReportGenerationAttemptRecord.operation_id)).where(
                ReportGenerationAttemptRecord.task_id == task_id,
                ReportGenerationAttemptRecord.status.in_(("PENDING", "SUCCEEDED")),
            )
        ) or 0
        if used >= limit:
            raise ProviderBudgetExceeded("Report draft limit reached")
        attempt = ReportGenerationAttemptRecord(
            operation_id=operation_id,
            task_id=task_id,
            status="PENDING",
            started_at=now,
            expires_at=now + timedelta(seconds=timeout_seconds),
        )
        self.session.add(attempt)
        self.session.commit()
        return attempt

    def finish(self, operation_id: UUID, status: str, reason: str | None = None) -> None:
        attempt = self.session.get(ReportGenerationAttemptRecord, operation_id)
        if attempt is None or attempt.status != "PENDING":
            return
        attempt.status = status
        attempt.finished_at = datetime.now(UTC)
        attempt.error_reason = reason
        self.session.commit()
