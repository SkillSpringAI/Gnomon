"""Fail-closed loading contracts for persisted security state."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from research_agent.application.security_capability import (
    SecurityCapability,
    SecurityCapabilityDenied,
    require_capability,
)
from research_agent.application.security_state_store import (
    SecurityStateStore,
    SecurityStateUnavailable,
)
from research_agent.persistence.models import SecurityStateRecord


class SessionDouble:
    def __init__(self, record: SecurityStateRecord | None) -> None:
        self.record = record

    def get(
        self, model: object, key: int, *, populate_existing: bool = False
    ) -> SecurityStateRecord | None:
        assert model is SecurityStateRecord
        assert key == 1
        assert populate_existing
        return self.record


def record(state: str = "normal", version: int = 1) -> SecurityStateRecord:
    return SecurityStateRecord(
        id=1,
        state=state,
        version=version,
        authority_epoch_id=uuid4(),
        updated_at=datetime.now(UTC),
        recovery_bootstrap_pending=False,
        recovery_bootstrap_started_at=None,
        recovery_bootstrap_from_state=None,
        recovery_bootstrap_from_version=None,
    )


def test_load_returns_persisted_state_without_defaulting() -> None:
    loaded = SecurityStateStore(SessionDouble(record("lockdown", 4))).load()
    assert loaded.state.value == "lockdown"
    assert loaded.version == 4
    assert loaded.identity == (loaded.authority_epoch_id, 4)


@pytest.mark.parametrize("epoch", [None, "not-a-uuid", str(uuid4()), UUID(int=0)])
def test_invalid_epoch_denies_loading_and_capabilities(epoch) -> None:
    persisted = record()
    persisted.authority_epoch_id = epoch
    with pytest.raises(SecurityStateUnavailable):
        SecurityStateStore(SessionDouble(persisted)).load()
    for capability in SecurityCapability:
        with pytest.raises(SecurityCapabilityDenied):
            require_capability(SessionDouble(persisted), capability)


def test_valid_epoch_is_not_a_capability_grant() -> None:
    persisted = record("lockdown")
    assert SecurityStateStore(SessionDouble(persisted)).load().authority_epoch_id
    with pytest.raises(SecurityCapabilityDenied):
        require_capability(SessionDouble(persisted), SecurityCapability.PROVIDER_DISPATCH)


def test_pending_recovery_bootstrap_makes_historical_normal_restrictive() -> None:
    persisted = record("normal", 7)
    persisted.recovery_bootstrap_pending = True
    persisted.recovery_bootstrap_started_at = datetime.now(UTC)
    persisted.recovery_bootstrap_from_state = "normal"
    persisted.recovery_bootstrap_from_version = 6
    loaded = SecurityStateStore(SessionDouble(persisted)).load()
    assert loaded.state.value == "recovery_required"
    assert loaded.version == 7
    assert loaded.recovery_bootstrap_pending
    with pytest.raises(SecurityCapabilityDenied):
        require_capability(SessionDouble(persisted), SecurityCapability.PROVIDER_DISPATCH)


@pytest.mark.parametrize(
    "pending,started,state,version",
    [
        (True, None, "normal", 1),
        (True, datetime.now(UTC), "unknown", 1),
        (True, datetime.now(UTC), "normal", 0),
        (False, datetime.now(UTC), None, None),
    ],
)
def test_invalid_recovery_bootstrap_metadata_fails_closed(pending, started, state, version) -> None:
    persisted = record()
    persisted.recovery_bootstrap_pending = pending
    persisted.recovery_bootstrap_started_at = started
    persisted.recovery_bootstrap_from_state = state
    persisted.recovery_bootstrap_from_version = version
    with pytest.raises(SecurityStateUnavailable):
        SecurityStateStore(SessionDouble(persisted)).load()


@pytest.mark.parametrize(
    "persisted",
    [None, record("unknown"), record("normal", 0)],
)
def test_missing_or_invalid_state_fails_closed(
    persisted: SecurityStateRecord | None,
) -> None:
    with pytest.raises(SecurityStateUnavailable):
        SecurityStateStore(SessionDouble(persisted)).load()
