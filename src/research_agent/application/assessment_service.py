"""Compatibility API for governed hypothesis assessments."""

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_agent.application.memory_service import MemoryService
from research_agent.domain.memory import MemoryAuthority, MemoryChangeProposal
from research_agent.domain.research import HypothesisAssessmentCreate, HypothesisAssessmentResponse
from research_agent.persistence.models import HypothesisAssessmentRecord, ResearchTaskRecord


class AssessmentNotFound(Exception):
    """Raised when an assessment target is invalid."""


class AssessmentService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save(
        self, task_id: UUID, hypothesis_id: UUID, assessment: HypothesisAssessmentCreate
    ) -> HypothesisAssessmentResponse:
        try:
            task = self.session.scalar(
                select(ResearchTaskRecord)
                .where(ResearchTaskRecord.id == task_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if task is None or not any(
                h["id"] == str(hypothesis_id) for h in task.brief["hypotheses"]
            ):
                raise AssessmentNotFound
            record = self.session.scalar(
                select(HypothesisAssessmentRecord)
                .where(
                    HypothesisAssessmentRecord.task_id == task_id,
                    HypothesisAssessmentRecord.hypothesis_id == hypothesis_id,
                )
                .execution_options(populate_existing=True)
            )
            target_id = record.id if record else uuid4()
            proposal = MemoryChangeProposal.model_validate(
                {
                    "target_type": "assessment",
                    "target_id": target_id,
                    "operation": "UPDATE" if record else "CREATE",
                    "expected_version": record.version if record else 0,
                    "hypothesis_id": None if record else hypothesis_id,
                    "reason": "Operator assessment submission",
                    "assessment": assessment,
                }
            )
            MemoryService(self.session).stage(
                proposal, MemoryAuthority("local_operator", task_id, can_commit=True)
            )
            record = self.session.get(HypothesisAssessmentRecord, target_id)
            if record is None:
                raise RuntimeError("Assessment creation did not produce a governed record")
            response = HypothesisAssessmentResponse.model_validate(
                {
                    **assessment.model_dump(),
                    "id": record.id,
                    "task_id": task_id,
                    "hypothesis_id": hypothesis_id,
                    "updated_at": record.updated_at,
                    "version": record.version,
                    "lifecycle": record.lifecycle,
                }
            )
            self.session.commit()
            return response
        except Exception:
            self.session.rollback()
            raise
