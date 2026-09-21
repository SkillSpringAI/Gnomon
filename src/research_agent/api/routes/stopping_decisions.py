"""Task-scoped stopping-decision and readiness endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from research_agent.application.stopping_decision_service import (
    StoppingDecisionConflict,
    StoppingDecisionNotFound,
    StoppingDecisionService,
)
from research_agent.domain.research import (
    StoppingDecision,
    StoppingDecisionChange,
    StoppingDecisionCreate,
    StoppingReadiness,
)
from research_agent.persistence.database import get_session

router = APIRouter(prefix="/investigations/{task_id}/stopping-decision", tags=["stopping"])


@router.get("/readiness", response_model=StoppingReadiness)
def readiness(
    task_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> StoppingReadiness:
    try:
        return StoppingDecisionService(session).readiness(task_id)
    except StoppingDecisionNotFound as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.get("", response_model=StoppingDecision)
def get_decision(
    task_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> StoppingDecision:
    try:
        return StoppingDecisionService(session).get(task_id)
    except StoppingDecisionNotFound as exc:
        raise HTTPException(status_code=404, detail="Stopping decision not found") from exc


@router.get("/history", response_model=list[StoppingDecisionChange])
def history(
    task_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> list[StoppingDecisionChange]:
    try:
        return StoppingDecisionService(session).history(task_id)
    except StoppingDecisionNotFound as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.post("", response_model=StoppingDecision, status_code=201)
def decide(
    task_id: UUID,
    request: StoppingDecisionCreate,
    session: Annotated[Session, Depends(get_session)],
) -> StoppingDecision:
    try:
        return StoppingDecisionService(session).decide(task_id, request)
    except StoppingDecisionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except StoppingDecisionNotFound as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
