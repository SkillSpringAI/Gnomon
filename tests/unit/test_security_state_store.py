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


@pytest.mark.parametrize(
    "persisted",
    [None, record("unknown"), record("normal", 0)],
)
def test_missing_or_invalid_state_fails_closed(
    persisted: SecurityStateRecord | None,
) -> None:
    with pytest.raises(SecurityStateUnavailable):
        SecurityStateStore(SessionDouble(persisted)).load()
