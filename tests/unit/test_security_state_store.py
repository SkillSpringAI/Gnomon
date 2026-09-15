"""Fail-closed loading contracts for persisted security state."""

from datetime import UTC, datetime

import pytest

from research_agent.application.security_state_store import (
    SecurityStateStore,
    SecurityStateUnavailable,
)
from research_agent.persistence.models import SecurityStateRecord


class SessionDouble:
    def __init__(self, record: SecurityStateRecord | None) -> None:
        self.record = record

    def get(self, model: object, key: int) -> SecurityStateRecord | None:
        assert model is SecurityStateRecord
        assert key == 1
        return self.record


def record(state: str = "normal", version: int = 1) -> SecurityStateRecord:
    return SecurityStateRecord(
        id=1,
        state=state,
        version=version,
        updated_at=datetime.now(UTC),
    )


def test_load_returns_persisted_state_without_defaulting() -> None:
    loaded = SecurityStateStore(SessionDouble(record("lockdown", 4))).load()
    assert loaded.state.value == "lockdown"
    assert loaded.version == 4


@pytest.mark.parametrize(
    "persisted",
    [None, record("unknown"), record("normal", 0)],
)
def test_missing_or_invalid_state_fails_closed(
    persisted: SecurityStateRecord | None,
) -> None:
    with pytest.raises(SecurityStateUnavailable):
        SecurityStateStore(SessionDouble(persisted)).load()
