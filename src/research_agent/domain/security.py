"""Canonical operational security states and their structural transitions."""

from enum import StrEnum


class SecurityState(StrEnum):
    """Persisted operational security states, independent of task lifecycle."""

    NORMAL = "normal"
    DEGRADED = "degraded"
    COMPROMISED_SUSPECTED = "compromised_suspected"
    LOCKDOWN = "lockdown"
    RECOVERY_REQUIRED = "recovery_required"


VALID_TRANSITIONS: dict[SecurityState, frozenset[SecurityState]] = {
    SecurityState.NORMAL: frozenset(
        {
            SecurityState.DEGRADED,
            SecurityState.COMPROMISED_SUSPECTED,
            SecurityState.LOCKDOWN,
        }
    ),
    SecurityState.DEGRADED: frozenset(
        {
            SecurityState.NORMAL,
            SecurityState.COMPROMISED_SUSPECTED,
            SecurityState.LOCKDOWN,
            SecurityState.RECOVERY_REQUIRED,
        }
    ),
    SecurityState.COMPROMISED_SUSPECTED: frozenset(
        {SecurityState.LOCKDOWN, SecurityState.RECOVERY_REQUIRED}
    ),
    SecurityState.LOCKDOWN: frozenset({SecurityState.RECOVERY_REQUIRED}),
    SecurityState.RECOVERY_REQUIRED: frozenset(
        {
            SecurityState.NORMAL,
            SecurityState.DEGRADED,
            SecurityState.COMPROMISED_SUSPECTED,
            SecurityState.LOCKDOWN,
        }
    ),
}


def is_valid_transition(current: SecurityState, requested: SecurityState) -> bool:
    """Return structural legality only; authorization is a separate concern."""
    return requested in VALID_TRANSITIONS[current]
