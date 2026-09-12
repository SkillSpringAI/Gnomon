"""Read persisted evidence using task-scoped bulk queries."""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_agent.domain.research import (
    AssessmentEvidenceLink,
    ClaimResponse,
    ClaimSourceLink,
    HypothesisAssessmentResponse,
    SourceResponse,
)
from research_agent.domain.snapshot import HypothesisSnapshot, InvestigationSnapshot
from research_agent.persistence.models import (
    AssessmentEvidenceRecord,
    ClaimSourceRecord,
    HypothesisAssessmentRecord,
    ResearchClaimRecord,
    ResearchSourceRecord,
)
from research_agent.persistence.repositories import SqlAlchemyResearchTaskRepository


class SnapshotService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, task_id: UUID) -> InvestigationSnapshot:
        task = SqlAlchemyResearchTaskRepository(self.session).get(task_id)
        sources = self.session.scalars(
            select(ResearchSourceRecord)
            .where(ResearchSourceRecord.task_id == task_id)
            .order_by(ResearchSourceRecord.observed_at, ResearchSourceRecord.id)
        ).all()
        claims = self.session.scalars(
            select(ResearchClaimRecord)
            .where(
                ResearchClaimRecord.task_id == task_id, ResearchClaimRecord.lifecycle == "active"
            )
            .order_by(ResearchClaimRecord.created_at, ResearchClaimRecord.id)
        ).all()
        source_links: dict[UUID, list[ClaimSourceLink]] = defaultdict(list)
        for link in self.session.scalars(
            select(ClaimSourceRecord)
            .join(ResearchClaimRecord, ResearchClaimRecord.id == ClaimSourceRecord.claim_id)
            .join(ResearchSourceRecord, ResearchSourceRecord.id == ClaimSourceRecord.source_id)
            .where(
                ResearchClaimRecord.task_id == task_id,
                ResearchSourceRecord.task_id == task_id,
            )
            .order_by(ClaimSourceRecord.claim_id, ClaimSourceRecord.source_id)
        ):
            source_links[link.claim_id].append(
                ClaimSourceLink.model_validate(link, from_attributes=True)
            )
        evidence_links: dict[UUID, list[AssessmentEvidenceLink]] = defaultdict(list)
        for evidence in self.session.scalars(
            select(AssessmentEvidenceRecord)
            .join(
                HypothesisAssessmentRecord,
                HypothesisAssessmentRecord.id == AssessmentEvidenceRecord.assessment_id,
            )
            .join(ResearchClaimRecord, ResearchClaimRecord.id == AssessmentEvidenceRecord.claim_id)
            .where(
                HypothesisAssessmentRecord.task_id == task_id,
                ResearchClaimRecord.task_id == task_id,
            )
            .order_by(AssessmentEvidenceRecord.assessment_id, AssessmentEvidenceRecord.claim_id)
        ):
            evidence_links[evidence.assessment_id].append(
                AssessmentEvidenceLink.model_validate(evidence, from_attributes=True)
            )
        assessments = {
            record.hypothesis_id: HypothesisAssessmentResponse.model_validate(
                {
                    "id": record.id,
                    "task_id": record.task_id,
                    "hypothesis_id": record.hypothesis_id,
                    "status": record.status,
                    "summary": record.summary,
                    "confidence": record.confidence,
                    "updated_at": record.updated_at,
                    "version": record.version,
                    "lifecycle": record.lifecycle,
                    "evidence_links": evidence_links[record.id],
                }
            )
            for record in self.session.scalars(
                select(HypothesisAssessmentRecord).where(
                    HypothesisAssessmentRecord.task_id == task_id,
                    HypothesisAssessmentRecord.lifecycle == "active",
                )
            )
        }
        return InvestigationSnapshot(
            task=task,
            hypotheses=[
                HypothesisSnapshot(
                    hypothesis=hypothesis,
                    assessment_state="assessed" if hypothesis.id in assessments else "not_assessed",
                    assessment=assessments.get(hypothesis.id),
                )
                for hypothesis in task.brief.hypotheses
            ],
            claims=[
                ClaimResponse.model_validate(
                    {
                        "id": claim.id,
                        "task_id": claim.task_id,
                        "statement": claim.statement,
                        "confidence": claim.confidence,
                        "status": claim.status,
                        "created_at": claim.created_at,
                        "version": claim.version,
                        "lifecycle": claim.lifecycle,
                        "source_links": source_links[claim.id],
                    }
                )
                for claim in claims
            ],
            sources=[
                SourceResponse.model_validate(source, from_attributes=True) for source in sources
            ],
            open_questions=task.plan.open_questions,
        )
