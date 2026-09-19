"""Operator-visible security state and explicitly requested transitions."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from research_agent.application.security_capability import (
    SecurityCapability,
    require_capability,
)
from research_agent.application.security_state_service import (
    SecurityStateConflict,
    SecurityStateTransitionService,
    SecurityTransitionDenied,
)
from research_agent.application.security_state_store import SecurityStateStore
from research_agent.domain.security import SecurityActor, SecurityReasonCode, SecurityState
from research_agent.persistence.database import SessionFactory
from research_agent.persistence.models import SecurityTransitionRecord

router = APIRouter(prefix="/security", tags=["security"])


class SecurityTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1, strict=True)
    requested_state: SecurityState
    reason_code: SecurityReasonCode


class SecurityStateResponse(BaseModel):
    state: SecurityState
    version: int
    authority_epoch_id: UUID


class SecurityTransitionResponse(BaseModel):
    transition_id: UUID | None
    previous_state: SecurityState
    new_state: SecurityState
    reason_code: SecurityReasonCode
    actor_type: SecurityActor
    actor_id: str
    created_at: datetime | None
    security_state_version: int
    authority_epoch_id: UUID | None
    related_event_ids: list[str]


@router.get("/state", response_model=SecurityStateResponse)
def get_security_state() -> SecurityStateResponse:
    with SessionFactory() as session:
        try:
            state = SecurityStateStore(session).load()
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Security state is unavailable",
            ) from exc
    return SecurityStateResponse(
        state=state.state, version=state.version, authority_epoch_id=state.authority_epoch_id.value
    )


@router.get("/transitions", response_model=list[SecurityTransitionResponse])
def list_security_transitions(limit: int = 100) -> list[SecurityTransitionResponse]:
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
    with SessionFactory() as session:
        require_capability(session, SecurityCapability.READ_AUDIT)
        records = session.scalars(
            select(SecurityTransitionRecord)
            .order_by(SecurityTransitionRecord.created_at.desc())
            .limit(limit)
        ).all()
    return [
        SecurityTransitionResponse.model_validate(record, from_attributes=True)
        for record in records
    ]


@router.post("/transitions", response_model=SecurityTransitionResponse)
def transition_security_state(request: SecurityTransitionRequest) -> SecurityTransitionResponse:
    with SessionFactory() as session:
        try:
            result = SecurityStateTransitionService(session).transition(
                expected_version=request.expected_version,
                requested_state=request.requested_state,
                actor_type=SecurityActor.LOCAL_OPERATOR,
                actor_id="api:local_operator",
                reason_code=request.reason_code,
            )
        except SecurityStateConflict as exc:
            raise HTTPException(status_code=409, detail="Security state version conflict") from exc
        except SecurityTransitionDenied as exc:
            raise HTTPException(status_code=403, detail="Security transition denied") from exc
        if result.transition_id is None:
            return SecurityTransitionResponse(
                transition_id=None,
                previous_state=result.state,
                new_state=result.state,
                reason_code=request.reason_code,
                actor_type=SecurityActor.LOCAL_OPERATOR,
                actor_id="api:local_operator",
                created_at=None,
                security_state_version=result.version,
                authority_epoch_id=result.authority_epoch_id.value,
                related_event_ids=[],
            )
        record = session.get(SecurityTransitionRecord, result.transition_id)
        if record is None:
            raise HTTPException(status_code=500, detail="Security transition audit unavailable")
        return SecurityTransitionResponse.model_validate(record, from_attributes=True)
