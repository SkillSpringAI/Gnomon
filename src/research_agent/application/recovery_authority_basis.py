"""Current recovery basis construction after caller-owned locking and READ_AUDIT."""

from sqlalchemy.orm import Session

from research_agent.application.security_state_store import SecurityStateStore
from research_agent.domain.recovery import RecoveryAuthorityBasis, RecoveryBootstrapOrigin
from research_agent.domain.security import SecurityState
from research_agent.persistence.models import SecurityStateRecord


def read_recovery_authority_basis(
    session: Session,
    record: SecurityStateRecord | None,
    *,
    unavailable: type[RuntimeError],
    missing_record_message: str | None = None,
) -> RecoveryAuthorityBasis:
    """Load and construct a basis without acquiring locks or owning a transaction.

    The caller must first lock singleton authority and require READ_AUDIT. Preserve
    the second state load before checking the locked row, including its refresh.
    The result is diagnostic evidence and does not authorize recovery actions.
    """
    current = SecurityStateStore(session).load()
    if missing_record_message is not None and record is None:
        raise unavailable(missing_record_message)
    assert record is not None  # Missing singleton was rejected by the capability guard.
    origin = None
    if current.recovery_bootstrap_pending:
        if (
            record.recovery_bootstrap_from_version is None
            or record.recovery_bootstrap_started_at is None
            or record.recovery_bootstrap_from_state is None
        ):
            raise unavailable("Bootstrap origin is missing")
        origin = RecoveryBootstrapOrigin(
            state=SecurityState(record.recovery_bootstrap_from_state),
            version=record.recovery_bootstrap_from_version,
            started_at=record.recovery_bootstrap_started_at,
        )
    return RecoveryAuthorityBasis(
        security_state_id=1,
        authority_epoch_id=current.authority_epoch_id.value,
        state=current.state,
        version=current.version,
        recovery_bootstrap_pending=current.recovery_bootstrap_pending,
        bootstrap_origin=origin,
    )
