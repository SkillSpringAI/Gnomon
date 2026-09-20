"""Startup-only authority boundary for fresh, continuing, and recovery bootstraps."""

from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_agent.application.security_state_store import (
    PersistedSecurityState,
    SecurityStateStore,
)
from research_agent.domain.research import utc_now
from research_agent.domain.security import AuthorityEpochId, SecurityState
from research_agent.persistence.models import (
    MemoryChangeRecord,
    ResearchTaskRecord,
    SecurityStateRecord,
    SecurityTransitionRecord,
    TrustedSourceRecord,
)


class AuthorityStartupMode(StrEnum):
    FRESH = "fresh"
    CONTINUING = "continuing"
    RECOVERY = "recovery"


class AuthorityBootstrapUnavailable(RuntimeError):
    """The requested startup authority boundary cannot be established safely."""


class AuthorityBootstrapService:
    """Establish effective authority before the HTTP application accepts requests."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def initialize(self, mode: AuthorityStartupMode) -> PersistedSecurityState:
        try:
            record = self.session.scalar(
                select(SecurityStateRecord)
                .where(SecurityStateRecord.id == 1)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if record is None:
                raise AuthorityBootstrapUnavailable("Canonical security state is unavailable")
            self._validate_record(record)
            if mode is AuthorityStartupMode.FRESH:
                self._require_pristine(record)
                self.session.rollback()
            elif mode is AuthorityStartupMode.CONTINUING:
                self.session.rollback()
            elif not record.recovery_bootstrap_pending:
                record.recovery_bootstrap_pending = True
                record.recovery_bootstrap_started_at = utc_now()
                record.recovery_bootstrap_from_state = record.state
                record.recovery_bootstrap_from_version = record.version
                record.version += 1
                record.updated_at = utc_now()
                self.session.commit()
            else:
                self.session.rollback()
            return SecurityStateStore(self.session).load()
        except Exception:
            self.session.rollback()
            raise

    @staticmethod
    def _validate_record(record: SecurityStateRecord) -> None:
        try:
            SecurityState(record.state)
            AuthorityEpochId(record.authority_epoch_id)
        except (TypeError, ValueError) as exc:
            raise AuthorityBootstrapUnavailable("Canonical authority is invalid") from exc
        if record.version < 1:
            raise AuthorityBootstrapUnavailable("Canonical authority version is invalid")

    def _require_pristine(self, record: SecurityStateRecord) -> None:
        has_history = any(
            self.session.scalar(select(model).limit(1)) is not None
            for model in (
                ResearchTaskRecord.id,
                TrustedSourceRecord.id,
                MemoryChangeRecord.change_id,
                SecurityTransitionRecord.transition_id,
            )
        )
        if (
            record.state != SecurityState.NORMAL.value
            or record.version != 1
            or record.recovery_bootstrap_pending
            or has_history
        ):
            raise AuthorityBootstrapUnavailable(
                "Fresh bootstrap requires a pristine newly migrated deployment"
            )
