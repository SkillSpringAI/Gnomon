"""Structural Slice 13.1 security-state transition contracts."""

import pytest

from research_agent.domain.security import (
    VALID_TRANSITIONS,
    SecurityState,
    is_valid_transition,
)

EXPECTED_TRANSITIONS = {
    SecurityState.NORMAL: {
        SecurityState.DEGRADED,
        SecurityState.COMPROMISED_SUSPECTED,
        SecurityState.LOCKDOWN,
    },
    SecurityState.DEGRADED: {
        SecurityState.NORMAL,
        SecurityState.COMPROMISED_SUSPECTED,
        SecurityState.LOCKDOWN,
        SecurityState.RECOVERY_REQUIRED,
    },
    SecurityState.COMPROMISED_SUSPECTED: {
        SecurityState.LOCKDOWN,
        SecurityState.RECOVERY_REQUIRED,
    },
    SecurityState.LOCKDOWN: {SecurityState.RECOVERY_REQUIRED},
    SecurityState.RECOVERY_REQUIRED: {
        SecurityState.NORMAL,
        SecurityState.DEGRADED,
        SecurityState.COMPROMISED_SUSPECTED,
        SecurityState.LOCKDOWN,
    },
}


def test_canonical_states_and_transition_map_match_slice_contract() -> None:
    assert set(SecurityState) == set(EXPECTED_TRANSITIONS)
    assert VALID_TRANSITIONS == {
        state: frozenset(targets) for state, targets in EXPECTED_TRANSITIONS.items()
    }


@pytest.mark.parametrize(
    ("current", "requested"),
    [
        (current, requested)
        for current, requested_states in EXPECTED_TRANSITIONS.items()
        for requested in requested_states
    ],
)
def test_each_documented_transition_is_allowed(
    current: SecurityState, requested: SecurityState
) -> None:
    assert is_valid_transition(current, requested)


def test_forbidden_transitions_and_same_state_are_denied() -> None:
    for current in SecurityState:
        assert not is_valid_transition(current, current)
        for requested in SecurityState:
            if requested not in EXPECTED_TRANSITIONS[current]:
                assert not is_valid_transition(current, requested)
