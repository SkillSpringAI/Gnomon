"""Post-restoration authority epoch replacement for M1.6."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Engine, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from research_agent.application.security_capability import SecurityCapability, require_capability
from research_agent.application.security_state_store import SecurityStateStore
from research_agent.domain.recovery import AuthorityEpochReplacementResult, ReplaceAuthorityEpoch
from research_agent.domain.security import SecurityActor, SecurityState
from research_agent.persistence.models import SecurityStateRecord, SecurityTransitionRecord

_ACTOR_ID = "local-authority-epoch-replacement"


class AuthorityEpochReplacementDenied(RuntimeError):
    """Epoch replacement preconditions are incomplete, stale or malformed."""


class AuthorityEpochReplacementService:
    """Create a new authority epoch without rewriting historical attribution."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @contextmanager
    def _transaction(self) -> Iterator[Session]:
        try:
            with self.engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
                with Session(bind=conn) as session, session.begin():
                    yield session
        except IntegrityError as exc:
            raise AuthorityEpochReplacementDenied("Authority epoch audit failed") from exc
        except DBAPIError as exc:
            if getattr(exc.orig, "sqlstate", None) in {"40001", "40P01"}:
                raise AuthorityEpochReplacementDenied("Authority snapshot changed") from exc
            raise

    def replace(self, request: ReplaceAuthorityEpoch) -> AuthorityEpochReplacementResult:
        request = ReplaceAuthorityEpoch.model_validate(request)
        with self._transaction() as session:
            return self._replace_locked(session, request)

    @staticmethod
    def _replace_locked(
        session: Session, request: ReplaceAuthorityEpoch
    ) -> AuthorityEpochReplacementResult:
        record = session.scalar(
            select(SecurityStateRecord)
            .where(SecurityStateRecord.id == 1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        require_capability(session, SecurityCapability.READ_AUDIT)
        current = SecurityStateStore(session).load()
        if record is None:
            raise AuthorityEpochReplacementDenied("Security state is unavailable")
        if current.state is not SecurityState.NORMAL or current.recovery_bootstrap_pending:
            raise AuthorityEpochReplacementDenied("Authority is not restored to NORMAL")
        if current.authority_epoch_id.value != request.expected_current_epoch_id:
            raise AuthorityEpochReplacementDenied("Expected authority epoch is stale")
        if current.version != request.expected_security_state_version:
            raise AuthorityEpochReplacementDenied("Expected security-state version is stale")
        restoration_audit = session.get(
            SecurityTransitionRecord,
            request.restoration_transition_id,
        )
        if (
            restoration_audit is None
            or restoration_audit.previous_state != SecurityState.RECOVERY_REQUIRED.value
            or restoration_audit.new_state != SecurityState.NORMAL.value
            or restoration_audit.authority_epoch_id != request.expected_current_epoch_id
            or str(request.restoration_id) not in restoration_audit.related_event_ids
        ):
            raise AuthorityEpochReplacementDenied("Restoration audit is not valid evidence")
        transition_id = uuid4()
        new_version = current.version + 1
        replaced_at = datetime.now(UTC)
        record.authority_epoch_id = request.new_authority_epoch_id
        record.version = new_version
        record.updated_at = replaced_at
        session.add(
            SecurityTransitionRecord(
                transition_id=transition_id,
                previous_state=SecurityState.NORMAL.value,
                new_state=SecurityState.NORMAL.value,
                reason_code=request.reason_code.value,
                actor_type=SecurityActor.SECURITY_RECOVERY_SERVICE.value,
                actor_id=_ACTOR_ID,
                created_at=replaced_at,
                security_state_version=new_version,
                authority_epoch_id=request.new_authority_epoch_id,
                related_event_ids=[
                    str(request.replacement_id),
                    str(request.restoration_id),
                    str(request.restoration_transition_id),
                    str(request.expected_current_epoch_id),
                ],
            )
        )
        session.flush()
        return AuthorityEpochReplacementResult(
            replacement_id=request.replacement_id,
            restoration_id=request.restoration_id,
            transition_id=transition_id,
            previous_authority_epoch_id=request.expected_current_epoch_id,
            authority_epoch_id=request.new_authority_epoch_id,
            version=new_version,
            replaced_at=replaced_at,
        )
