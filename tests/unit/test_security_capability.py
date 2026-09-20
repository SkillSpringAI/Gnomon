from itertools import product

import pytest

from research_agent.application.security_capability import (
    AuthorityDirection,
    SecurityCapability,
    SecurityCapabilityDenied,
    allows,
    require_capability,
)
from research_agent.domain.security import SecurityState


@pytest.mark.parametrize("state", list(SecurityState))
def test_safe_capabilities_remain_available(state: SecurityState) -> None:
    for capability in (
        SecurityCapability.READ_STATE,
        SecurityCapability.READ_AUDIT,
        SecurityCapability.LOCAL_REPORT,
        SecurityCapability.DIAGNOSTICS,
    ):
        assert allows(state, capability)


@pytest.mark.parametrize("state", list(SecurityState)[1:])
def test_restrictive_states_deny_authority_bearing_capabilities(state: SecurityState) -> None:
    for capability in (
        SecurityCapability.MEMORY_MUTATION,
        SecurityCapability.START_CYCLE,
        SecurityCapability.SOURCE_RETRIEVAL,
        SecurityCapability.PROVIDER_DISPATCH,
        SecurityCapability.AGENT_DISPATCH,
    ):
        assert not allows(state, capability)


@pytest.mark.parametrize(
    "state,capability,direction",
    product(SecurityState, SecurityCapability, AuthorityDirection),
)
def test_directional_capability_matrix_fails_closed(state, capability, direction) -> None:
    safe = {
        SecurityCapability.READ_STATE,
        SecurityCapability.READ_AUDIT,
        SecurityCapability.LOCAL_REPORT,
        SecurityCapability.DIAGNOSTICS,
    }
    ordinary = {
        SecurityCapability.MEMORY_MUTATION,
        SecurityCapability.START_CYCLE,
        SecurityCapability.SOURCE_RETRIEVAL,
        SecurityCapability.PROVIDER_DISPATCH,
        SecurityCapability.AGENT_DISPATCH,
    }
    if capability in safe:
        expected = True
    elif capability in ordinary:
        expected = state is SecurityState.NORMAL
    elif capability is SecurityCapability.SECURITY_CONTAINMENT:
        expected = direction in {AuthorityDirection.REDUCE, AuthorityDirection.PRESERVE}
    elif capability is SecurityCapability.RECOVERY_ACTION:
        expected = state is not SecurityState.NORMAL and direction is AuthorityDirection.PRESERVE
    else:
        expected = direction in {AuthorityDirection.REDUCE, AuthorityDirection.PRESERVE} or (
            direction is AuthorityDirection.BROADEN
            and state
            in {SecurityState.NORMAL, SecurityState.DEGRADED, SecurityState.RECOVERY_REQUIRED}
        )
    assert allows(state, capability, direction) is expected


@pytest.mark.parametrize("state", list(SecurityState))
def test_containment_never_broadens_and_directional_defaults_deny(state) -> None:
    assert not allows(
        state, SecurityCapability.SECURITY_CONTAINMENT, AuthorityDirection.BROADEN
    )
    for capability in (
        SecurityCapability.SECURITY_CONTAINMENT,
        SecurityCapability.RECOVERY_ACTION,
        SecurityCapability.AUTHORITY_ADMINISTRATION,
    ):
        assert not allows(state, capability)


@pytest.mark.parametrize("state,capability", product(SecurityState, SecurityCapability))
def test_unknown_direction_fails_closed(state, capability) -> None:
    assert not allows(state, capability, "unknown")  # type: ignore[arg-type]


def test_recovery_action_is_not_a_normal_state_superuser() -> None:
    for direction in AuthorityDirection:
        assert not allows(SecurityState.NORMAL, SecurityCapability.RECOVERY_ACTION, direction)


def test_missing_state_fails_closed() -> None:
    class MissingStateSession:
        def get(self, *_: object, **__: object) -> None:
            return None

    with pytest.raises(SecurityCapabilityDenied):
        require_capability(MissingStateSession(), SecurityCapability.PROVIDER_DISPATCH)  # type: ignore[arg-type]
