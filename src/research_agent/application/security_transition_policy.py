"""Explicit state/actor/reason authorization and current capability direction."""

from research_agent.application.security_capability import AuthorityDirection
from research_agent.domain.security import SecurityActor, SecurityReasonCode, SecurityState


def authority_direction(current: SecurityState, requested: SecurityState) -> AuthorityDirection:
    """Classify capability effect independently of structural legality or permission."""
    if current is SecurityState.NORMAL and requested is not SecurityState.NORMAL:
        return AuthorityDirection.REDUCE
    if current is not SecurityState.NORMAL and requested is SecurityState.NORMAL:
        return AuthorityDirection.BROADEN
    return AuthorityDirection.PRESERVE


_FINDINGS = frozenset(
    {
        SecurityReasonCode.SECURITY_INVARIANT_VIOLATION,
        SecurityReasonCode.INTEGRITY_CHECK_FAILED,
        SecurityReasonCode.CREDENTIAL_COMPROMISE_SUSPECTED,
        SecurityReasonCode.AUTHORITY_BOUNDARY_VIOLATION,
    }
)
_DEGRADED = {
    SecurityActor.LOCAL_OPERATOR: frozenset(
        {
            SecurityReasonCode.OPERATOR_DEGRADED_MODE,
            SecurityReasonCode.SECURITY_DEPENDENCY_DEGRADED,
        }
    ),
    SecurityActor.SECURITY_DETECTOR: frozenset({SecurityReasonCode.SECURITY_DEPENDENCY_DEGRADED}),
}
_SUSPECTED = {
    SecurityActor.LOCAL_OPERATOR: _FINDINGS,
    SecurityActor.SECURITY_DETECTOR: _FINDINGS,
}
_LOCKDOWN = {
    SecurityActor.LOCAL_OPERATOR: _FINDINGS | {SecurityReasonCode.OPERATOR_LOCKDOWN},
    SecurityActor.SECURITY_DETECTOR: _FINDINGS,
}
_RECOVERY = {
    SecurityActor.LOCAL_OPERATOR: frozenset({SecurityReasonCode.RECOVERY_STARTED}),
    SecurityActor.SECURITY_RECOVERY_SERVICE: frozenset({SecurityReasonCode.RECOVERY_STARTED}),
}
_NORMAL = {
    SecurityActor.LOCAL_OPERATOR: frozenset({SecurityReasonCode.RECOVERY_VERIFIED}),
    SecurityActor.SECURITY_RECOVERY_SERVICE: frozenset({SecurityReasonCode.RECOVERY_VERIFIED}),
}

# Enumerate edges explicitly so extending the structural graph grants no new authority.
_MATRIX = {
    (SecurityState.NORMAL, SecurityState.DEGRADED): _DEGRADED,
    (SecurityState.NORMAL, SecurityState.COMPROMISED_SUSPECTED): _SUSPECTED,
    (SecurityState.NORMAL, SecurityState.LOCKDOWN): _LOCKDOWN,
    (SecurityState.DEGRADED, SecurityState.NORMAL): _NORMAL,
    (SecurityState.DEGRADED, SecurityState.COMPROMISED_SUSPECTED): _SUSPECTED,
    (SecurityState.DEGRADED, SecurityState.LOCKDOWN): _LOCKDOWN,
    (SecurityState.DEGRADED, SecurityState.RECOVERY_REQUIRED): _RECOVERY,
    (SecurityState.COMPROMISED_SUSPECTED, SecurityState.LOCKDOWN): _LOCKDOWN,
    (SecurityState.COMPROMISED_SUSPECTED, SecurityState.RECOVERY_REQUIRED): _RECOVERY,
    (SecurityState.LOCKDOWN, SecurityState.RECOVERY_REQUIRED): _RECOVERY,
    (SecurityState.RECOVERY_REQUIRED, SecurityState.NORMAL): _NORMAL,
    (SecurityState.RECOVERY_REQUIRED, SecurityState.DEGRADED): _DEGRADED,
    (SecurityState.RECOVERY_REQUIRED, SecurityState.COMPROMISED_SUSPECTED): _SUSPECTED,
    (SecurityState.RECOVERY_REQUIRED, SecurityState.LOCKDOWN): _LOCKDOWN,
}


def authorized_transition(
    current: SecurityState,
    requested: SecurityState,
    actor: SecurityActor,
    reason: SecurityReasonCode,
) -> bool:
    """Deny any state-changing tuple absent from the explicit matrix."""
    return reason in _MATRIX.get((current, requested), {}).get(actor, frozenset())
