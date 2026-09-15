import pytest

from research_agent.application.security_capability import (
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
        SecurityCapability.SECURITY_CONTAINMENT,
        SecurityCapability.RECOVERY_ACTION,
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


def test_missing_state_fails_closed() -> None:
    class MissingStateSession:
        def get(self, *_: object) -> None:
            return None

    with pytest.raises(SecurityCapabilityDenied):
        require_capability(MissingStateSession(), SecurityCapability.PROVIDER_DISPATCH)  # type: ignore[arg-type]
