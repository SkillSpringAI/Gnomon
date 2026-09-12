"""Operator memory proposals; authority never comes from the request payload."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from research_agent.application.memory_service import MemoryService
from research_agent.application.research_service import ResearchTaskNotFound
from research_agent.domain.memory import (
    AppliedMemoryChange,
    MemoryAuthority,
    MemoryChangeProposal,
    MemoryReversal,
    MemoryValidation,
)
from research_agent.persistence.database import get_session
from research_agent.persistence.models import MemoryChangeRecord

router = APIRouter(prefix="/investigations/{task_id}/memory", tags=["memory"])


def operator_authority(task_id: UUID) -> MemoryAuthority:
    """Existing single-operator API boundary, not multi-user authentication."""
    return MemoryAuthority("local_operator", task_id, can_commit=True)


@router.post("/validate", response_model=MemoryValidation)
def validate(
    proposal: MemoryChangeProposal,
    session: Annotated[Session, Depends(get_session)],
    authority: Annotated[MemoryAuthority, Depends(operator_authority)],
) -> MemoryValidation:
    try:
        MemoryService(session).validate(proposal, authority)
        return MemoryValidation(valid=True, reason="Valid now; commit revalidates")
    except ResearchTaskNotFound as exc:
        raise HTTPException(404, "Investigation not found") from exc
    except ValueError as exc:
        raise HTTPException(422, "Invalid memory provenance or payload") from exc


@router.post("/changes", response_model=AppliedMemoryChange)
def commit(
    proposal: MemoryChangeProposal,
    session: Annotated[Session, Depends(get_session)],
    authority: Annotated[MemoryAuthority, Depends(operator_authority)],
) -> AppliedMemoryChange:
    try:
        return MemoryService(session).apply(proposal, authority)
    except ResearchTaskNotFound as exc:
        raise HTTPException(404, "Investigation not found") from exc
    except ValueError as exc:
        raise HTTPException(422, "Invalid memory provenance or payload") from exc


@router.get("/changes/{change_id}", response_model=AppliedMemoryChange)
def history(
    change_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    authority: Annotated[MemoryAuthority, Depends(operator_authority)],
) -> AppliedMemoryChange:
    if not authority.can_commit or authority.actor != "local_operator":
        raise HTTPException(403, "History requires operator authority")
    record = session.scalar(
        select(MemoryChangeRecord).where(
            MemoryChangeRecord.change_id == change_id,
            MemoryChangeRecord.task_id == authority.task_id,
        )
    )
    if record is None:
        raise HTTPException(404, "Change not found")
    return AppliedMemoryChange.model_validate(record, from_attributes=True)


@router.post("/changes/{change_id}/reverse", response_model=AppliedMemoryChange)
def reverse(
    change_id: UUID,
    request: MemoryReversal,
    session: Annotated[Session, Depends(get_session)],
    authority: Annotated[MemoryAuthority, Depends(operator_authority)],
) -> AppliedMemoryChange:
    try:
        return MemoryService(session).reverse(change_id, request, authority)
    except ResearchTaskNotFound as exc:
        raise HTTPException(404, "Investigation not found") from exc
    except ValueError as exc:
        raise HTTPException(422, "Invalid memory provenance or payload") from exc
