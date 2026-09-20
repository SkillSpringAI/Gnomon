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


class SecurityCapabilityDenied(RuntimeError):
    """The current persisted security state does not permit a capability."""


def require_locked_capability(
    session: Session, capability: SecurityCapability
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
    if not allows(current.state, capability):
        raise SecurityCapabilityDenied("Security policy denied capability")
    return current


_ALWAYS_SAFE = {
    SecurityCapability.READ_STATE,
    SecurityCapability.READ_AUDIT,
    SecurityCapability.LOCAL_REPORT,
    SecurityCapability.DIAGNOSTICS,
    SecurityCapability.SECURITY_CONTAINMENT,
    SecurityCapability.RECOVERY_ACTION,
}
_RESTRICTED = {
    SecurityCapability.MEMORY_MUTATION,
    SecurityCapability.START_CYCLE,
    SecurityCapability.SOURCE_RETRIEVAL,
    SecurityCapability.PROVIDER_DISPATCH,
    SecurityCapability.AGENT_DISPATCH,
}


def allows(state: SecurityState, capability: SecurityCapability) -> bool:
    """Return the explicit baseline policy decision for one state/capability pair."""
    if capability in _ALWAYS_SAFE:
        return True
    if state is SecurityState.NORMAL:
        return True
    return capability not in _RESTRICTED


def require_capability(session: Session, capability: SecurityCapability) -> SecurityState:
    """Load state fail-closed and reject a capability before its side effect."""
    try:
        current = SecurityStateStore(session).load()
    except SecurityStateUnavailable as exc:
        raise SecurityCapabilityDenied("Security state is unavailable; capability denied") from exc
    if not allows(current.state, capability):
        raise SecurityCapabilityDenied(
            f"Capability {capability.value} is denied in security state {current.state.value}"
        )
    return current.state
