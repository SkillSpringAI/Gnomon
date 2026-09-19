"""Fail-closed loading for the persisted operational security state."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from research_agent.domain.security import AuthorityEpochId, SecurityState
from research_agent.persistence.models import SecurityStateRecord


class SecurityStateUnavailable(RuntimeError):
    """The canonical persisted security state cannot be trusted or loaded."""


@dataclass(frozen=True)
class PersistedSecurityState:
    state: SecurityState
    version: int
    authority_epoch_id: AuthorityEpochId

    @property
    def identity(self) -> tuple[AuthorityEpochId, int]:
        """A version identifies state only within its continuous lineage."""
        return self.authority_epoch_id, self.version


class SecurityStateStore:
    """Read the singleton state without inferring a default at runtime."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def load(self) -> PersistedSecurityState:
        # Point-of-effect checks must not reuse an earlier identity-map snapshot.
        record = self.session.get(SecurityStateRecord, 1, populate_existing=True)
        if record is None:
            raise SecurityStateUnavailable("Persisted security state is missing")
        try:
            state = SecurityState(record.state)
            epoch = AuthorityEpochId(record.authority_epoch_id)
        except ValueError as exc:
            raise SecurityStateUnavailable("Persisted security state is invalid") from exc
        if record.version < 1:
            raise SecurityStateUnavailable("Persisted security-state version is invalid")
        return PersistedSecurityState(state=state, version=record.version, authority_epoch_id=epoch)
