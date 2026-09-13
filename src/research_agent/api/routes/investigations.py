"""Investigation task endpoints."""

from collections.abc import Generator
from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from research_agent.adapters.agents.fake import FakeScenario
from research_agent.adapters.web.http import HttpSourceRetriever
from research_agent.api.routes.evidence import get_source_retriever
from research_agent.application.agent_cycle_runner import AgentCycleRunner
from research_agent.application.research_service import (
    CycleNotFound,
    InMemoryResearchTaskRepository,
    InvalidCycleSelection,
    ResearchService,
    ResearchTaskNotFound,
    TaskStateConflict,
)
from research_agent.application.source_cycle_runner import SourceCycleRequest, SourceCycleRunner
from research_agent.config.settings import get_settings
from research_agent.domain.research import (
    CycleOutcomeCreate,
    ResearchBrief,
    ResearchTaskResponse,
    TaskStatusChange,
)
from research_agent.persistence.database import SessionFactory, get_session
from research_agent.persistence.repositories import SqlAlchemyResearchTaskRepository

router: Final = APIRouter(prefix="/investigations", tags=["investigations"])


class AgentCycleRunRequest(BaseModel):
    """Local fake-network controls for one bounded cycle run."""

    model_config = ConfigDict(extra="forbid")

    scenario: FakeScenario = FakeScenario.HONEST
    max_agents: int = Field(default=2, ge=1, le=2)
    objective_indices: list[int] = Field(default_factory=lambda: [0], min_length=1, max_length=3)


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


@router.post("/{task_id}/cycles/{cycle_number}/start", response_model=ResearchTaskResponse)
def start_cycle(
    task_id: UUID,
    cycle_number: int,
    service: Annotated[ResearchService, Depends(get_research_service)],
) -> ResearchTaskResponse:
    """Mark a planned cycle as active."""
    try:
        return ResearchTaskResponse(task=service.start_cycle(task_id, cycle_number))
    except (ResearchTaskNotFound, CycleNotFound) as exc:
        raise HTTPException(status_code=404, detail="Cycle not found") from exc
    except TaskStateConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{task_id}/cycles/{cycle_number}/run", response_model=ResearchTaskResponse)
def run_agent_cycle(
    task_id: UUID,
    cycle_number: int,
    request: AgentCycleRunRequest,
    session: Annotated[Session, Depends(get_session)],
) -> ResearchTaskResponse:
    """Run one bounded cycle against the local fake agent network."""
    try:
        task = AgentCycleRunner(session).run(
            task_id,
            cycle_number,
            scenario=request.scenario,
            max_agents=request.max_agents,
            objective_indices=request.objective_indices,
        )
        return ResearchTaskResponse(task=task)
    except (ResearchTaskNotFound, CycleNotFound) as exc:
        raise HTTPException(status_code=404, detail="Cycle not found") from exc
    except TaskStateConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{task_id}/cycles/{cycle_number}/run-sources", response_model=ResearchTaskResponse)
def run_source_cycle(
    task_id: UUID,
    cycle_number: int,
    request: SourceCycleRequest,
    session: Annotated[Session, Depends(get_session)],
    retriever: Annotated[HttpSourceRetriever, Depends(get_source_retriever)],
) -> ResearchTaskResponse:
    """Retrieve up to two explicit URLs using the existing per-hop source policy."""
    try:
        return ResearchTaskResponse(
            task=SourceCycleRunner(session, retriever).run(task_id, cycle_number, request)
        )
    except (ResearchTaskNotFound, CycleNotFound) as exc:
        raise HTTPException(status_code=404, detail="Cycle not found") from exc
    except InvalidCycleSelection as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TaskStateConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{task_id}/cycles/{cycle_number}/outcome", response_model=ResearchTaskResponse)
def record_cycle_outcome(
    task_id: UUID,
    cycle_number: int,
    outcome: CycleOutcomeCreate,
    service: Annotated[ResearchService, Depends(get_research_service)],
) -> ResearchTaskResponse:
    """Record a bounded result and provenance for an active cycle."""
    try:
        return ResearchTaskResponse(
            task=service.record_cycle_outcome(task_id, cycle_number, outcome)
        )
    except (ResearchTaskNotFound, CycleNotFound) as exc:
        raise HTTPException(status_code=404, detail="Cycle not found") from exc
    except TaskStateConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
