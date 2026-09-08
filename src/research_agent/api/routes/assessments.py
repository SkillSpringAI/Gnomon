"""Hypothesis assessment endpoints."""

from collections.abc import Generator
from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from research_agent.application.assessment_service import AssessmentNotFound, AssessmentService
from research_agent.domain.research import HypothesisAssessmentCreate, HypothesisAssessmentResponse
from research_agent.persistence.database import SessionFactory

router: Final = APIRouter(prefix="/investigations/{task_id}", tags=["assessments"])


def get_assessment_service() -> Generator[AssessmentService, None, None]:
    """Provide the assessment service and close its session."""
    session = SessionFactory()
    try:
        yield AssessmentService(session)
    finally:
        session.close()


@router.put(
    "/hypotheses/{hypothesis_id}/assessment",
    response_model=HypothesisAssessmentResponse,
)
def save_assessment(
    task_id: UUID,
    hypothesis_id: UUID,
    assessment: HypothesisAssessmentCreate,
    service: Annotated[AssessmentService, Depends(get_assessment_service)],
) -> HypothesisAssessmentResponse:
    """Save the current evidence-backed assessment of a hypothesis."""
    try:
        return service.save(task_id, hypothesis_id, assessment)
    except AssessmentNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail="Investigation or hypothesis not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
