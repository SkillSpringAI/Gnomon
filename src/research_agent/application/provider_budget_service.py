"""Short task-serialized transactions for report execution and its audit."""

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from research_agent.application.audit_service import AuditService
from research_agent.application.research_service import ResearchTaskNotFound
from research_agent.domain.events import EventPayload, EventType
from research_agent.persistence.models import ReportGenerationAttemptRecord, ResearchTaskRecord


class ProviderBudgetExceeded(Exception):
    """No reservation capacity remains for this investigation."""


class ProviderAttemptConflict(Exception):
    """The operation identity or expected execution state conflicts."""


class ProviderBudgetService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _lock_task(self, task_id: UUID) -> None:
        if (
            self.session.scalar(
                select(ResearchTaskRecord.id)
                .where(ResearchTaskRecord.id == task_id)
                .with_for_update()
            )
            is None
        ):
            raise ResearchTaskNotFound("Investigation not found")

    def _lock_attempt(self, operation_id: UUID) -> ReportGenerationAttemptRecord:
        # Read identity only before locking: every writer locks task, then attempt.
        task_id = self.session.scalar(
            select(ReportGenerationAttemptRecord.task_id).where(
                ReportGenerationAttemptRecord.operation_id == operation_id
            )
        )
        if task_id is None:
            raise ProviderAttemptConflict("Provider attempt does not exist")
        self._lock_task(task_id)
        attempt = self.session.scalar(
            select(ReportGenerationAttemptRecord)
            .where(ReportGenerationAttemptRecord.operation_id == operation_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if attempt is None:
            raise ProviderAttemptConflict("Provider attempt does not exist")
        return attempt

    def _audit(
        self,
        attempt: ReportGenerationAttemptRecord,
        event: EventType,
        payload: EventPayload | None = None,
    ) -> None:
        AuditService(self.session).stage(
            attempt.task_id, event, payload or EventPayload(operation_id=attempt.operation_id)
        )

    def reserve(
        self, task_id: UUID, operation_id: UUID, limit: int, timeout_seconds: int
    ) -> ReportGenerationAttemptRecord:
        try:
            self._lock_task(task_id)
            if self.session.get(ReportGenerationAttemptRecord, operation_id) is not None:
                raise ProviderAttemptConflict("Operation ID has already been used")
            now = datetime.now(UTC)
            expired = self.session.scalars(
                select(ReportGenerationAttemptRecord)
                .where(
                    ReportGenerationAttemptRecord.task_id == task_id,
                    ReportGenerationAttemptRecord.status == "PENDING",
                    ReportGenerationAttemptRecord.expires_at <= now,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            ).all()
            for attempt in expired:
                attempt.status = "EXPIRED"
                attempt.finished_at = now
                attempt.error_reason = "reservation_expired"
                self._audit(attempt, EventType.REPORT_DRAFT_EXPIRED)
            self.session.flush()
            used = (
                self.session.scalar(
                    select(func.count(ReportGenerationAttemptRecord.operation_id)).where(
                        ReportGenerationAttemptRecord.task_id == task_id,
                        ReportGenerationAttemptRecord.status.in_(
                            ("PENDING", "DISPATCHED", "UNKNOWN", "SUCCEEDED")
                        ),
                    )
                )
                or 0
            )
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
            self._audit(attempt, EventType.REPORT_DRAFT_RESERVED)
            self.session.commit()
            return attempt
        except IntegrityError as exc:
            self.session.rollback()
            diagnostic = getattr(exc.orig, "diag", None)
            if getattr(diagnostic, "constraint_name", None) == "report_generation_attempts_pkey":
                raise ProviderAttemptConflict("Operation ID has already been used") from exc
            raise
        except Exception:
            self.session.rollback()
            raise

    def dispatch(self, operation_id: UUID) -> None:
        """Commit authorization before remote work; expired admission cannot dispatch."""
        try:
            attempt = self._lock_attempt(operation_id)
            if attempt.status != "PENDING":
                raise ProviderAttemptConflict("Provider attempt is no longer dispatchable")
            if attempt.expires_at <= datetime.now(UTC):
                attempt.status = "EXPIRED"
                attempt.finished_at = datetime.now(UTC)
                attempt.error_reason = "reservation_expired"
                self._audit(attempt, EventType.REPORT_DRAFT_EXPIRED)
                self.session.commit()
                raise ProviderAttemptConflict("Provider reservation expired before dispatch")
            attempt.status = "DISPATCHED"
            self._audit(attempt, EventType.REPORT_DRAFT_DISPATCHED)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def finish(
        self,
        operation_id: UUID,
        status: Literal["SUCCEEDED", "FAILED", "UNKNOWN"],
        reason: str | None = None,
        *,
        payload: EventPayload | None = None,
    ) -> None:
        """State and audit commit together; equal repeats are no-ops, conflicts fail."""
        try:
            attempt = self._lock_attempt(operation_id)
            if payload is not None and payload.operation_id != operation_id:
                raise ProviderAttemptConflict("Audit operation does not match attempt")
            if attempt.status == status:
                self.session.commit()
                return
            if status not in {"SUCCEEDED", "FAILED", "UNKNOWN"} or (
                attempt.status not in {"DISPATCHED", "UNKNOWN"}
                and not (attempt.status == "PENDING" and status == "FAILED")
            ):
                raise ProviderAttemptConflict("Provider attempt has a conflicting outcome")
            event = {
                "SUCCEEDED": EventType.REPORT_DRAFT_GENERATED,
                "FAILED": EventType.REPORT_DRAFT_FAILED,
                "UNKNOWN": EventType.REPORT_DRAFT_UNCERTAIN,
            }[status]
            attempt.status = status
            attempt.finished_at = None if status == "UNKNOWN" else datetime.now(UTC)
            attempt.error_reason = reason
            self._audit(attempt, event, payload)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def recover(self, task_id: UUID, operation_id: UUID) -> None:
        """Operator acknowledges an overdue dispatch; never refund an unknown outcome."""
        try:
            attempt = self._lock_attempt(operation_id)
            if attempt.task_id != task_id:
                raise ProviderAttemptConflict("Operation belongs to another investigation")
            if attempt.status == "UNKNOWN":
                self.session.commit()
                return
            if attempt.status != "DISPATCHED" or attempt.expires_at > datetime.now(UTC):
                raise ProviderAttemptConflict("Only an overdue dispatched attempt can be recovered")
            self.finish(
                operation_id,
                "UNKNOWN",
                "provider_outcome_unknown",
                payload=EventPayload(
                    operation_id=operation_id,
                    actor="local_operator",
                    reason="provider_outcome_unknown",
                ),
            )
        except Exception:
            self.session.rollback()
            raise
