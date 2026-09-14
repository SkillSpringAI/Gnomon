"""Durable cycle progress staged in the same transaction as its evidence."""

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_agent.application.audit_service import AuditService
from research_agent.application.research_service import TaskStateConflict
from research_agent.domain.events import EventPayload, EventType
from research_agent.domain.research import (
    ClaimResponse,
    CycleObjectiveResult,
    SourceResponse,
    utc_now,
)
from research_agent.persistence.models import (
    ResearchCycleAttemptRecord,
    ResearchCycleRecord,
    ResearchTaskRecord,
)


class CycleProgress:
    def __init__(self, session: Session, task_id: UUID, cycle_number: int) -> None:
        self.session = session
        self.task_id = task_id
        self.cycle_number = cycle_number
        self.attempt_id: UUID | None = None

    def start(self) -> UUID:
        """Create the durable attempt before adapter work begins."""
        cycle = self.session.scalar(
            select(ResearchCycleRecord).where(
                ResearchCycleRecord.task_id == self.task_id,
                ResearchCycleRecord.cycle_number == self.cycle_number,
            )
        )
        if cycle is None:
            raise TaskStateConflict("Cycle does not exist")
        self.attempt_id = uuid4()
        self.session.add(
            ResearchCycleAttemptRecord(
                id=self.attempt_id,
                task_id=self.task_id,
                cycle_id=cycle.id,
                status="RUNNING",
                stage="STARTED",
                started_at=utc_now(),
            )
        )
        self.session.commit()
        return self.attempt_id

    def stage(self, stage: str) -> None:
        if self.attempt_id is None:
            raise TaskStateConflict("Cycle attempt has not been started")
        attempt = self.session.get(ResearchCycleAttemptRecord, self.attempt_id)
        if attempt is None or attempt.status != "RUNNING":
            raise TaskStateConflict("Cycle attempt is no longer running")
        attempt.stage = stage
        self.session.flush()

    def _stage(
        self,
        indices: list[int],
        source_ids: list[UUID],
        claim_ids: list[UUID],
    ) -> None:
        task = self.session.scalar(
            select(ResearchTaskRecord)
            .where(
                ResearchTaskRecord.id == self.task_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        cycle = self.session.scalar(
            select(ResearchCycleRecord)
            .where(
                ResearchCycleRecord.task_id == self.task_id,
                ResearchCycleRecord.cycle_number == self.cycle_number,
            )
            .execution_options(populate_existing=True)
        )
        if task is None or cycle is None or task.status != "active" or cycle.status != "active":
            raise TaskStateConflict("Investigation or cycle stopped before progress commit")
        if not indices or any(index < 0 or index >= len(cycle.objectives) for index in indices):
            raise ValueError("Progress requires saved objective indexes")
        saved = [CycleObjectiveResult.model_validate(item) for item in cycle.objective_results]
        results = {item.objective_index: item for item in saved}
        for index in indices:
            result = results.setdefault(index, CycleObjectiveResult(objective_index=index))
            result.source_ids = list(dict.fromkeys(result.source_ids + source_ids))
            result.claim_ids = list(dict.fromkeys(result.claim_ids + claim_ids))
        evidence = list(dict.fromkeys(cycle.evidence_ids + [str(item) for item in source_ids]))
        claims = list(dict.fromkeys(cycle.claim_ids + [str(item) for item in claim_ids]))
        if len(results) > 3 or len(evidence) > 100 or len(claims) > 100:
            raise ValueError("Cycle progress exceeds collection bounds")
        cycle.objective_results = [item.model_dump(mode="json") for item in results.values()]
        cycle.evidence_ids = evidence
        cycle.claim_ids = claims
        cycle.attempted_objectives = list(
            dict.fromkeys(cycle.objectives[index] for index in results)
        )
        cycle.unresolved_objectives = list(cycle.objectives)
        task.updated_at = utc_now()
        AuditService(self.session).stage(
            self.task_id,
            EventType.CYCLE_PROGRESS_RECORDED,
            EventPayload(
                operation_id=uuid4(),
                cycle_number=self.cycle_number,
                claim_count=len(claims),
                result="committed",
            ),
        )

    def attempt(self, indices: list[int]) -> None:
        """Reserve an attempt before adapter dispatch; release the task lock immediately."""
        try:
            if self.attempt_id is None:
                self.start()
            self._stage(indices, [], [])
            self.stage("QUESTIONING")
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def source(self, source: SourceResponse, indices: list[int]) -> None:
        # The caller owns the source transaction, including its rollback on failure.
        self._stage(indices, [source.id], [])
        self.stage("EVIDENCE_RECORDED")

    def claims(self, claims: list[ClaimResponse], indices: list[int]) -> None:
        self._stage(indices, [], [claim.id for claim in claims])
        self.stage("EXTRACTING_CLAIMS")

    def finish(self, status: str, reason: str | None = None) -> None:
        if self.attempt_id is None:
            return
        attempt = self.session.get(ResearchCycleAttemptRecord, self.attempt_id)
        if attempt is not None and attempt.status == "RUNNING":
            attempt.status = status.upper()
            attempt.stage = status.upper()
            attempt.finished_at = utc_now()
            attempt.recovery_reason = reason
            self.session.flush()
