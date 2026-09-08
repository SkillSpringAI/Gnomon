"""Read the task-scoped audit trail without returning evidence bodies."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from research_agent.application.audit_service import AuditService
from research_agent.application.research_service import ResearchTaskNotFound
from research_agent.domain.events import ResearchEventResponse
from research_agent.persistence.database import get_session

router = APIRouter(prefix="/investigations", tags=["investigations"])


@router.get(
    "/{task_id}/events",
    response_model=list[ResearchEventResponse],
    response_model_exclude_none=True,
)
def list_events(
    task_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ResearchEventResponse]:
    try:
        return AuditService(session).list_events(task_id, limit, offset)
    except ResearchTaskNotFound as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
