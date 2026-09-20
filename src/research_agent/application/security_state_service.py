"""Authorized compare-and-set transitions for the canonical security state."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from research_agent.application.persistence_error_translation import translate_integrity_error
from research_agent.application.security_capability import (
    AuthorityDirection,
    SecurityCapability,
    SecurityCapabilityDenied,
    allows,
)
from research_agent.application.security_transition_policy import (
    authority_direction,
    authorized_transition,
)
from research_agent.domain.research import utc_now
from research_agent.domain.security import (
    AuthorityEpochId,
    SecurityActor,
    SecurityReasonCode,
    SecurityState,
    is_valid_transition,
)
from research_agent.persistence.models import SecurityStateRecord, SecurityTransitionRecord


class SecurityStateConflict(RuntimeError):
    """The caller's expected version is not the persisted version."""


class SecurityTransitionDenied(RuntimeError):
    """The requested transition is structurally or authoritatively invalid."""


@dataclass(frozen=True)
class SecurityTransitionResult:
    state: SecurityState
    version: int
    transition_id: UUID | None
    authority_epoch_id: AuthorityEpochId


class SecurityStateTransitionService:
    """Perform one locked state update and its authoritative audit append."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def transition(
        self,
        *,
        expected_version: int,
        requested_state: SecurityState,
        actor_type: SecurityActor,
        actor_id: str,
        reason_code: SecurityReasonCode,
        related_event_ids: list[UUID] | None = None,
    ) -> SecurityTransitionResult:
        if expected_version < 1 or not actor_id.strip():
            raise SecurityTransitionDenied("Transition request metadata is invalid")
        record = self.session.scalar(
            select(SecurityStateRecord)
            .where(SecurityStateRecord.id == 1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if record is None:
            raise SecurityTransitionDenied("Persisted security state is unavailable")
        if record.recovery_bootstrap_pending:
            raise SecurityTransitionDenied("Recovery bootstrap is pending reconciliation")
        try:
            current = SecurityState(record.state)
            epoch = AuthorityEpochId(record.authority_epoch_id)
        except ValueError as exc:
            raise SecurityTransitionDenied("Persisted security state is invalid") from exc
        if record.version < 1:
            raise SecurityTransitionDenied("Persisted security-state version is invalid")
        if record.version != expected_version:
            raise SecurityStateConflict(
                f"Expected security-state version {expected_version}, found {record.version}"
            )
        if requested_state == current:
            # Rollback expires ORM attributes and releases the row lock. Capture
            # the entire observed identity before another transition can commit.
            version = record.version
            self.session.rollback()
            return SecurityTransitionResult(current, version, None, epoch)
        if not is_valid_transition(current, requested_state):
            raise SecurityTransitionDenied(f"Invalid transition {current} -> {requested_state}")
        if not self._authorized(current, requested_state, actor_type, reason_code):
            raise SecurityTransitionDenied("Actor is not authorized for this transition")
        direction = authority_direction(current, requested_state)
        required = [(SecurityCapability.AUTHORITY_ADMINISTRATION, direction)]
        if (
            direction is AuthorityDirection.BROADEN
            or requested_state is SecurityState.RECOVERY_REQUIRED
        ):
            # Recovery purpose remains non-authoritative: administration separately
            # authorizes the actual direction-bearing state modification above.
            required.append((SecurityCapability.RECOVERY_ACTION, AuthorityDirection.PRESERVE))
        else:
            required.append((SecurityCapability.SECURITY_CONTAINMENT, direction))
        for capability, capability_direction in required:
            if not allows(current, capability, capability_direction):
                raise SecurityCapabilityDenied(
                    f"Capability {capability.value} is denied in security state {current.value}"
                )

        transition_id = uuid4()
        new_version = record.version + 1
        record.state = requested_state.value
        record.version = new_version
        record.updated_at = utc_now()
        self.session.add(
            SecurityTransitionRecord(
                transition_id=transition_id,
                previous_state=current.value,
                new_state=requested_state.value,
                reason_code=reason_code.value,
                actor_type=actor_type.value,
                actor_id=actor_id,
                created_at=utc_now(),
                security_state_version=new_version,
                authority_epoch_id=epoch.value,
                related_event_ids=[str(event_id) for event_id in (related_event_ids or [])],
            )
        )
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            translate_integrity_error(exc)
        except Exception:
            self.session.rollback()
            raise
        return SecurityTransitionResult(requested_state, new_version, transition_id, epoch)

    @staticmethod
    def _authorized(
        current: SecurityState,
        requested: SecurityState,
        actor: SecurityActor,
        reason: SecurityReasonCode,
    ) -> bool:
        return authorized_transition(current, requested, actor, reason)
