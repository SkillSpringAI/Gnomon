"""Centralized capability decisions derived from the persisted security state."""

from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_agent.application.security_state_store import (
    PersistedSecurityState,
    SecurityStateStore,
    SecurityStateUnavailable,
)
from research_agent.domain.security import SecurityState
from research_agent.persistence.models import SecurityStateRecord


class SecurityCapability(StrEnum):
    READ_STATE = "read_state"
    READ_AUDIT = "read_audit"
    LOCAL_REPORT = "local_report"
    DIAGNOSTICS = "diagnostics"
    MEMORY_MUTATION = "memory_mutation"
    START_CYCLE = "start_cycle"
    SOURCE_RETRIEVAL = "source_retrieval"
    PROVIDER_DISPATCH = "provider_dispatch"
    AGENT_DISPATCH = "agent_dispatch"
    SECURITY_CONTAINMENT = "security_containment"
    RECOVERY_ACTION = "recovery_action"
    AUTHORITY_ADMINISTRATION = "authority_administration"


class AuthorityDirection(StrEnum):
    """Direction of an authority-bearing effect, not a credential or purpose."""

    REDUCE = "reduce"
    PRESERVE = "preserve"
    BROADEN = "broaden"


class SecurityCapabilityDenied(RuntimeError):
    """The current persisted security state does not permit a capability."""


def require_locked_capability(
    session: Session,
    capability: SecurityCapability,
    direction: AuthorityDirection | None = None,
) -> PersistedSecurityState:
    """After locking the task, hold a security SHARE lock through the caller's commit.

    Security transitions take FOR UPDATE on this same row. No adapter calls may
    occur in this transaction. This function never commits or grants write scope.
    """
    with session.no_autoflush:
        record = session.scalar(
            select(SecurityStateRecord)
            .where(SecurityStateRecord.id == 1)
            .with_for_update(read=True)
            .execution_options(populate_existing=True)
        )
        if record is None:
            raise SecurityCapabilityDenied("Security state is unavailable; capability denied")
        try:
            current = SecurityStateStore(session).load()
        except SecurityStateUnavailable as exc:
            raise SecurityCapabilityDenied(
                "Security state is unavailable; capability denied"
            ) from exc
    if not allows(current.state, capability, direction):
        raise SecurityCapabilityDenied("Security policy denied capability")
    return current


_ALWAYS_SAFE = {
    SecurityCapability.READ_STATE,
    SecurityCapability.READ_AUDIT,
    SecurityCapability.LOCAL_REPORT,
    SecurityCapability.DIAGNOSTICS,
}
_RESTRICTED = {
    SecurityCapability.MEMORY_MUTATION,
    SecurityCapability.START_CYCLE,
    SecurityCapability.SOURCE_RETRIEVAL,
    SecurityCapability.PROVIDER_DISPATCH,
    SecurityCapability.AGENT_DISPATCH,
}

_DIRECTIONAL = {
    SecurityCapability.SECURITY_CONTAINMENT,
    SecurityCapability.RECOVERY_ACTION,
    SecurityCapability.AUTHORITY_ADMINISTRATION,
}


def allows(
    state: SecurityState,
    capability: SecurityCapability,
    direction: AuthorityDirection | None = None,
) -> bool:
    """Return one explicit state/capability/direction policy decision."""
    if not isinstance(state, SecurityState) or not isinstance(capability, SecurityCapability):
        return False
    if direction is not None and not isinstance(direction, AuthorityDirection):
        return False
    if capability in _ALWAYS_SAFE:
        return True
    if capability in _DIRECTIONAL and direction is None:
        return False
    if capability is SecurityCapability.SECURITY_CONTAINMENT:
        return direction in {AuthorityDirection.REDUCE, AuthorityDirection.PRESERVE}
    if capability is SecurityCapability.RECOVERY_ACTION:
        return state is not SecurityState.NORMAL and direction is AuthorityDirection.PRESERVE
    if capability is SecurityCapability.AUTHORITY_ADMINISTRATION:
        if direction in {AuthorityDirection.REDUCE, AuthorityDirection.PRESERVE}:
            return True
        return direction is AuthorityDirection.BROADEN and state in {
            SecurityState.NORMAL,
            SecurityState.DEGRADED,
            SecurityState.RECOVERY_REQUIRED,
        }
    if state is SecurityState.NORMAL:
        return True
    return capability not in _RESTRICTED


def require_capability(
    session: Session,
    capability: SecurityCapability,
    direction: AuthorityDirection | None = None,
) -> SecurityState:
    """Load state fail-closed and reject a capability before its side effect."""
    try:
        current = SecurityStateStore(session).load()
    except SecurityStateUnavailable as exc:
        raise SecurityCapabilityDenied("Security state is unavailable; capability denied") from exc
    if not allows(current.state, capability, direction):
        raise SecurityCapabilityDenied(
            f"Capability {capability.value} is denied in security state {current.state.value}"
        )
    return current.state
