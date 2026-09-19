"""Canonical operational security states and their structural transitions."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


@dataclass(frozen=True)
class AuthorityEpochId:
    """Continuous authority lineage identity; possession grants no capability."""

    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID) or self.value.int == 0:
            raise ValueError("Authority epoch must be a non-nil UUID")


class SecurityState(StrEnum):
    """Persisted operational security states, independent of task lifecycle."""

    NORMAL = "normal"
    DEGRADED = "degraded"
    COMPROMISED_SUSPECTED = "compromised_suspected"
    LOCKDOWN = "lockdown"
    RECOVERY_REQUIRED = "recovery_required"


class SecurityActor(StrEnum):
    """Trusted principals permitted to request security-state transitions."""

    LOCAL_OPERATOR = "local_operator"
    SECURITY_DETECTOR = "security_detector"
    SECURITY_RECOVERY_SERVICE = "security_recovery_service"


class SecurityReasonCode(StrEnum):
    """Bounded, non-content-bearing reasons for a security transition."""

    OPERATOR_LOCKDOWN = "OPERATOR_LOCKDOWN"
    SECURITY_INVARIANT_VIOLATION = "SECURITY_INVARIANT_VIOLATION"
    INTEGRITY_CHECK_FAILED = "INTEGRITY_CHECK_FAILED"
    CREDENTIAL_COMPROMISE_SUSPECTED = "CREDENTIAL_COMPROMISE_SUSPECTED"
    AUTHORITY_BOUNDARY_VIOLATION = "AUTHORITY_BOUNDARY_VIOLATION"
    SECURITY_DEPENDENCY_DEGRADED = "SECURITY_DEPENDENCY_DEGRADED"
    RECOVERY_STARTED = "RECOVERY_STARTED"
    RECOVERY_VERIFIED = "RECOVERY_VERIFIED"
    RECOVERY_PARTIAL = "RECOVERY_PARTIAL"
    RECOVERY_FAILED = "RECOVERY_FAILED"
    OPERATOR_DEGRADED_MODE = "OPERATOR_DEGRADED_MODE"


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
