"""Application service for evidence-backed hypothesis assessments."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_agent.domain.research import (
    HypothesisAssessmentCreate,
    HypothesisAssessmentResponse,
    HypothesisAssessmentStatus,
)
from research_agent.persistence.models import (
    AssessmentEvidenceRecord,
    HypothesisAssessmentRecord,
    ResearchClaimRecord,
    ResearchTaskRecord,
)


class AssessmentNotFound(Exception):
    """Raised when an assessment target is invalid."""


class AssessmentService:
    """Validate and persist current hypothesis assessments."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(
        self,
        task_id: UUID,
        hypothesis_id: UUID,
        assessment: HypothesisAssessmentCreate,
    ) -> HypothesisAssessmentResponse:
        task = self.session.scalar(
            select(ResearchTaskRecord)
            .where(ResearchTaskRecord.id == task_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        has_hypothesis = task is not None and any(
            hypothesis["id"] == str(hypothesis_id) for hypothesis in task.brief["hypotheses"]
        )
        if not has_hypothesis:
            raise AssessmentNotFound

        claim_ids = {link.claim_id for link in assessment.evidence_links}
        claims = self.session.scalars(
            select(ResearchClaimRecord).where(
                ResearchClaimRecord.id.in_(claim_ids),
                ResearchClaimRecord.task_id == task_id,
            )
        ).all()
        if len(claims) != len(claim_ids):
            raise ValueError("Every assessment claim must belong to the same investigation")

        record = self.session.scalar(
            select(HypothesisAssessmentRecord).where(
                HypothesisAssessmentRecord.task_id == task_id,
                HypothesisAssessmentRecord.hypothesis_id == hypothesis_id,
            )
        )
        now = datetime.now(UTC)
        if record is None:
            record = HypothesisAssessmentRecord(
                id=uuid4(),
                task_id=task_id,
                hypothesis_id=hypothesis_id,
                status=assessment.status.value,
                summary=assessment.summary,
                confidence=assessment.confidence,
                updated_at=now,
            )
            self.session.add(record)
        else:
            record.status = assessment.status.value
            record.summary = assessment.summary
            record.confidence = assessment.confidence
            record.updated_at = now

        self.session.flush()
        self.session.query(AssessmentEvidenceRecord).filter_by(assessment_id=record.id).delete()
        self.session.add_all(
            AssessmentEvidenceRecord(
                assessment_id=record.id,
                claim_id=link.claim_id,
                relation=link.relation.value,
                strength=link.strength,
            )
            for link in assessment.evidence_links
        )
        self.session.commit()
        return HypothesisAssessmentResponse(
            id=record.id,
            task_id=task_id,
            hypothesis_id=hypothesis_id,
            status=HypothesisAssessmentStatus(record.status),
            summary=record.summary,
            confidence=record.confidence,
            evidence_links=assessment.evidence_links,
            updated_at=record.updated_at,
        )
