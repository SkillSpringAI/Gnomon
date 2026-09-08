"""Investigation task endpoints."""

from collections.abc import Generator
from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from research_agent.application.research_service import (
    InMemoryResearchTaskRepository,
    ResearchService,
    ResearchTaskNotFound,
    TaskStateConflict,
)
from research_agent.config.settings import get_settings
from research_agent.domain.research import ResearchBrief, ResearchTaskResponse, TaskStatusChange
from research_agent.persistence.database import SessionFactory
from research_agent.persistence.repositories import SqlAlchemyResearchTaskRepository

router: Final = APIRouter(prefix="/investigations", tags=["investigations"])


def get_research_service() -> Generator[ResearchService, None, None]:
    """Provide the configured research service and close database sessions."""
    settings = get_settings()
    if settings.persistence_backend == "memory":
        yield ResearchService(InMemoryResearchTaskRepository())
        return

    session = SessionFactory()
    try:
        yield ResearchService(SqlAlchemyResearchTaskRepository(session))
    finally:
        session.close()


@router.post("", response_model=ResearchTaskResponse, status_code=status.HTTP_201_CREATED)
def create_investigation(
    brief: ResearchBrief,
    service: Annotated[ResearchService, Depends(get_research_service)],
) -> ResearchTaskResponse:
    """Create an open-ended investigation and its first research cycle."""
    return ResearchTaskResponse(task=service.create_task(brief))


@router.get("/{task_id}", response_model=ResearchTaskResponse)
def get_investigation(
    task_id: UUID,
    service: Annotated[ResearchService, Depends(get_research_service)],
) -> ResearchTaskResponse:
    """Return the current state of an investigation."""
    try:
        return ResearchTaskResponse(task=service.get_task(task_id))
    except ResearchTaskNotFound as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.post("/{task_id}/cycles", response_model=ResearchTaskResponse)
def plan_next_cycle(
    task_id: UUID,
    service: Annotated[ResearchService, Depends(get_research_service)],
) -> ResearchTaskResponse:
    """Create the next bounded research cycle for an investigation."""
    try:
        return ResearchTaskResponse(task=service.plan_next_cycle(task_id))
    except ResearchTaskNotFound as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except TaskStateConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/{task_id}/status", response_model=ResearchTaskResponse)
def change_status(
    task_id: UUID,
    change: TaskStatusChange,
    service: Annotated[ResearchService, Depends(get_research_service)],
) -> ResearchTaskResponse:
    """Change lifecycle status with stale-state protection."""
    try:
        return ResearchTaskResponse(task=service.change_status(task_id, change))
    except ResearchTaskNotFound as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except TaskStateConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
