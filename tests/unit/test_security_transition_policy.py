"""Exhaustive actor/reason policy contract, including every rejected tuple."""

from itertools import product

import pytest

from research_agent.application.security_transition_policy import (
    AuthorityDirection,
    authority_direction,
    authorized_transition,
)
from research_agent.domain.security import SecurityActor, SecurityReasonCode, SecurityState

# Independent specification, using public wire values rather than policy internals.
EDGES = {
    "normal": {"degraded", "compromised_suspected", "lockdown"},
    "degraded": {"normal", "compromised_suspected", "lockdown", "recovery_required"},
    "compromised_suspected": {"lockdown", "recovery_required"},
    "lockdown": {"recovery_required"},
    "recovery_required": {"normal", "degraded", "compromised_suspected", "lockdown"},
}
FINDINGS = {
    "SECURITY_INVARIANT_VIOLATION",
    "INTEGRITY_CHECK_FAILED",
    "CREDENTIAL_COMPROMISE_SUSPECTED",
    "AUTHORITY_BOUNDARY_VIOLATION",
}
REASONS = {
    ("degraded", "local_operator"): {"OPERATOR_DEGRADED_MODE", "SECURITY_DEPENDENCY_DEGRADED"},
    ("degraded", "security_detector"): {"SECURITY_DEPENDENCY_DEGRADED"},
    ("compromised_suspected", "local_operator"): FINDINGS,
    ("compromised_suspected", "security_detector"): FINDINGS,
    ("lockdown", "local_operator"): FINDINGS | {"OPERATOR_LOCKDOWN"},
    ("lockdown", "security_detector"): FINDINGS,
    ("recovery_required", "local_operator"): {"RECOVERY_STARTED"},
    ("recovery_required", "security_recovery_service"): {"RECOVERY_STARTED"},
    ("normal", "local_operator"): {"RECOVERY_VERIFIED"},
    ("normal", "security_recovery_service"): {"RECOVERY_VERIFIED"},
}


@pytest.mark.parametrize(
    "current,requested,actor,reason",
    product(SecurityState, SecurityState, SecurityActor, SecurityReasonCode),
)
def test_all_state_actor_reason_combinations(current, requested, actor, reason):
    expected = requested.value in EDGES[current.value] and reason.value in REASONS.get(
        (requested.value, actor.value), set()
    )
    assert authorized_transition(current, requested, actor, reason) is expected


@pytest.mark.parametrize("current,requested", product(SecurityState, repeat=2))
def test_direction_describes_current_capabilities_only(current, requested):
    expected = AuthorityDirection.PRESERVE
    if current is SecurityState.NORMAL and requested is not SecurityState.NORMAL:
        expected = AuthorityDirection.REDUCE
    elif current is not SecurityState.NORMAL and requested is SecurityState.NORMAL:
        expected = AuthorityDirection.BROADEN
    assert authority_direction(current, requested) is expected


def test_unknown_actor_or_reason_never_gains_authority():
    assert not authorized_transition(
        SecurityState.NORMAL,
        SecurityState.LOCKDOWN,
        "external_agent",
        SecurityReasonCode.OPERATOR_LOCKDOWN,
    )
    assert not authorized_transition(
        SecurityState.NORMAL, SecurityState.LOCKDOWN, SecurityActor.LOCAL_OPERATOR, "UNKNOWN_REASON"
    )
