"""Fail-closed loading for the persisted operational security state."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from research_agent.domain.security import SecurityState
from research_agent.persistence.models import SecurityStateRecord


class SecurityStateUnavailable(RuntimeError):
    """The canonical persisted security state cannot be trusted or loaded."""


@dataclass(frozen=True)
class PersistedSecurityState:
    state: SecurityState
    version: int


class SecurityStateStore:
    """Read the singleton state without inferring a default at runtime."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def load(self) -> PersistedSecurityState:
        record = self.session.get(SecurityStateRecord, 1)
        if record is None:
            raise SecurityStateUnavailable("Persisted security state is missing")
        try:
            state = SecurityState(record.state)
        except ValueError as exc:
            raise SecurityStateUnavailable("Persisted security state is invalid") from exc
        if record.version < 1:
            raise SecurityStateUnavailable("Persisted security-state version is invalid")
        return PersistedSecurityState(state=state, version=record.version)
