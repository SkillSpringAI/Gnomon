"""Task-scoped HTTP adapters for declared source dependence."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from research_agent.application.source_dependence_service import (
    SourceDependenceConflict,
    SourceDependenceNotFound,
    SourceDependenceService,
)
from research_agent.domain.research import (
    SourceDependenceProjection,
    SourceRelationship,
    SourceRelationshipChange,
    SourceRelationshipCreate,
    SourceRelationshipMutation,
    SourceRelationshipReversal,
)
from research_agent.persistence.database import get_session

router = APIRouter(
    prefix="/investigations/{task_id}/source-dependence",
    tags=["source-dependence"],
)


class SourceDependenceProjectionRequest(BaseModel):
    """Bounded task-local projection request."""

    model_config = ConfigDict(extra="forbid")

    root_source_ids: list[UUID] = Field(min_length=1, max_length=100)


def _conflict(exc: SourceDependenceConflict) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


@router.post("/relationships", response_model=SourceRelationship, status_code=201)
def create_relationship(
    task_id: UUID,
    request: SourceRelationshipCreate,
    session: Annotated[Session, Depends(get_session)],
) -> SourceRelationship:
    try:
        return SourceDependenceService(session).create(task_id, request)
    except SourceDependenceConflict as exc:
        raise _conflict(exc) from exc
    except SourceDependenceNotFound as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.get("/relationships/{relationship_id}", response_model=SourceRelationship)
def get_relationship(
    task_id: UUID,
    relationship_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> SourceRelationship:
    try:
        return SourceDependenceService(session).get(task_id, relationship_id)
    except SourceDependenceNotFound as exc:
        raise HTTPException(status_code=404, detail="Relationship not found") from exc


@router.get(
    "/relationships/{relationship_id}/history",
    response_model=list[SourceRelationshipChange],
)
def relationship_history(
    task_id: UUID,
    relationship_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> list[SourceRelationshipChange]:
    try:
        return SourceDependenceService(session).history(task_id, relationship_id)
    except SourceDependenceNotFound as exc:
        raise HTTPException(status_code=404, detail="Relationship not found") from exc


@router.patch("/relationships/{relationship_id}", response_model=SourceRelationship)
def mutate_relationship(
    task_id: UUID,
    relationship_id: UUID,
    request: SourceRelationshipMutation,
    session: Annotated[Session, Depends(get_session)],
) -> SourceRelationship:
    if request.relationship_id != relationship_id:
        raise HTTPException(status_code=422, detail="Relationship path and body must match")
    try:
        return SourceDependenceService(session).mutate(task_id, request)
    except SourceDependenceConflict as exc:
        raise _conflict(exc) from exc
    except SourceDependenceNotFound as exc:
        raise HTTPException(status_code=404, detail="Relationship not found") from exc


@router.post("/relationships/{relationship_id}/reverse", response_model=SourceRelationship)
def reverse_relationship(
    task_id: UUID,
    relationship_id: UUID,
    request: SourceRelationshipReversal,
    session: Annotated[Session, Depends(get_session)],
) -> SourceRelationship:
    if request.relationship_id != relationship_id:
        raise HTTPException(status_code=422, detail="Relationship path and body must match")
    try:
        return SourceDependenceService(session).reverse(task_id, request)
    except SourceDependenceConflict as exc:
        raise _conflict(exc) from exc
    except SourceDependenceNotFound as exc:
        raise HTTPException(status_code=404, detail="Relationship or change not found") from exc


@router.post("/projection", response_model=SourceDependenceProjection)
def project_dependence(
    task_id: UUID,
    request: SourceDependenceProjectionRequest,
    session: Annotated[Session, Depends(get_session)],
) -> SourceDependenceProjection:
    try:
        return SourceDependenceService(session).project(task_id, request.root_source_ids)
    except SourceDependenceConflict as exc:
        raise _conflict(exc) from exc
    except SourceDependenceNotFound as exc:
        raise HTTPException(status_code=404, detail="Investigation or source not found") from exc
