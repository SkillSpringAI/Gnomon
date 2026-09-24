"""Protected restoration preflight for M1.5 pass 1."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Engine, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from research_agent.application.authorization_service import (
    AuthorizationService,
    AuthorizationUnavailable,
)
from research_agent.application.recovery_context_service import (
    RecoveryContextService,
    RecoveryContextUnavailable,
)
from research_agent.application.recovery_reconciliation_service import (
    RecoveryReconciliationConflict,
    RecoveryReconciliationService,
)
from research_agent.application.security_capability import SecurityCapability, require_capability
from research_agent.application.security_state_store import SecurityStateStore
from research_agent.domain.authorization import (
    AuthorizationCapability,
    validate_execution_authorization,
)
from research_agent.domain.recovery import (
    PreparedProtectedRestoration,
    PrepareProtectedRestoration,
    ProtectedRestorationResult,
    ReconciliationOutcome,
    RecoveryAuthorityBasis,
    RecoveryBootstrapOrigin,
    RecoveryInventoryStatus,
    RecoveryReconciliation,
)
from research_agent.domain.research import utc_now
from research_agent.domain.security import SecurityActor, SecurityState
from research_agent.persistence.authorization import (
    ExecutionAuthorizationRecord,
    OperatorAuthorizationRecord,
)
from research_agent.persistence.models import SecurityStateRecord, SecurityTransitionRecord
from research_agent.persistence.recovery import RecoveryContextRecord


class ProtectedRestorationDenied(RuntimeError):
    """Restoration preconditions are incomplete, stale or malformed."""


class RecoveryRestorationService:
    """Validate restoration inputs together without clearing the recovery fence."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self._contexts = RecoveryContextService(engine)
        self._authorizations = AuthorizationService(engine)

    @contextmanager
    def _transaction(self) -> Iterator[Session]:
        try:
            with self.engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
                with Session(bind=conn) as session, session.begin():
                    yield session
        except DBAPIError as exc:
            if getattr(exc.orig, "sqlstate", None) in {"40001", "40P01"}:
                raise ProtectedRestorationDenied("Authority snapshot changed") from exc
            raise

    def prepare(self, request: PrepareProtectedRestoration) -> PreparedProtectedRestoration:
        request = PrepareProtectedRestoration.model_validate(request)
        with self._transaction() as session:
            prepared, _, _, _ = self._prepare_locked(session, request)
            return prepared

    def complete(self, request: PrepareProtectedRestoration) -> ProtectedRestorationResult:
        request = PrepareProtectedRestoration.model_validate(request)
        try:
            with self._transaction() as session:
                prepared, basis, record, checked_at = self._prepare_locked(session, request)
                transition_id = uuid4()
                new_version = basis.version + 1
                record.state = SecurityState.NORMAL.value
                record.version = new_version
                record.updated_at = utc_now()
                record.recovery_bootstrap_pending = False
                record.recovery_bootstrap_started_at = None
                record.recovery_bootstrap_from_state = None
                record.recovery_bootstrap_from_version = None
                session.add(
                    SecurityTransitionRecord(
                        transition_id=transition_id,
                        previous_state=SecurityState.RECOVERY_REQUIRED.value,
                        new_state=SecurityState.NORMAL.value,
                        reason_code=request.reason_code.value,
                        actor_type=SecurityActor.SECURITY_RECOVERY_SERVICE.value,
                        actor_id="local-recovery-restoration",
                        created_at=checked_at,
                        security_state_version=new_version,
                        authority_epoch_id=basis.authority_epoch_id,
                        related_event_ids=[
                            str(request.restoration_id),
                            str(request.context_id),
                            str(request.operator_authorization_id),
                            str(request.execution_authorization_id),
                        ],
                    )
                )
                session.flush()
                return ProtectedRestorationResult(
                    restoration_id=request.restoration_id,
                    context_id=prepared.context_id,
                    incident_id=prepared.incident_id,
                    transition_id=transition_id,
                    state=SecurityState.NORMAL,
                    version=new_version,
                    authority_epoch_id=basis.authority_epoch_id,
                    completed_at=checked_at,
                )
        except IntegrityError as exc:
            raise ProtectedRestorationDenied("Restoration audit failed") from exc

    def _prepare_locked(
        self,
        session: Session,
        request: PrepareProtectedRestoration,
    ) -> tuple[PreparedProtectedRestoration, RecoveryAuthorityBasis, SecurityStateRecord, datetime]:
        basis, record = self._locked_basis(session)
        if not basis.recovery_bootstrap_pending:
            raise ProtectedRestorationDenied("Recovery bootstrap is not pending")
        if basis.authority_epoch_id != request.expected_authority_epoch_id:
            raise ProtectedRestorationDenied("Expected authority epoch is stale")
        if basis.version != request.expected_security_state_version:
            raise ProtectedRestorationDenied("Expected security-state version is stale")
        context_record = session.get(RecoveryContextRecord, request.context_id)
        if context_record is None:
            raise ProtectedRestorationDenied("Recovery context not found")
        try:
            context = self._contexts._decode(session, context_record)
        except RecoveryContextUnavailable as exc:
            raise ProtectedRestorationDenied("Recovery context is invalid") from exc
        checked_at = datetime.now(UTC)
        reconciliation = self._reconcile(session, context.context_id, basis, checked_at)
        if not reconciliation.restoration_allowed:
            raise ProtectedRestorationDenied("Recovery reconciliation has not passed")
        operator_record = session.get(
            OperatorAuthorizationRecord,
            request.operator_authorization_id,
        )
        if operator_record is None:
            raise ProtectedRestorationDenied("Operator authorization not found")
        execution_record = session.get(
            ExecutionAuthorizationRecord,
            request.execution_authorization_id,
        )
        if execution_record is None:
            raise ProtectedRestorationDenied("Execution authorization not found")
        try:
            operator = self._authorizations._decode_operator(session, operator_record)
            execution = self._authorizations._decode_execution(session, execution_record)
            validate_execution_authorization(
                execution,
                operator,
                current_authority_epoch_id=basis.authority_epoch_id,
                now=checked_at,
            )
        except (AuthorizationUnavailable, ValueError) as exc:
            raise ProtectedRestorationDenied("Authorization evidence is invalid") from exc
        if (
            operator.recovery_context_id != context.context_id
            or execution.recovery_context_id != context.context_id
            or execution.granted_capability is not AuthorizationCapability.RECOVERY_ACTION
        ):
            raise ProtectedRestorationDenied("Authorization is not bound to this recovery action")
        return (
            PreparedProtectedRestoration(
                restoration_id=request.restoration_id,
                context_id=context.context_id,
                incident_id=context.incident_id,
                operator_authorization_id=operator.authorization_id,
                execution_authorization_id=execution.execution_authorization_id,
                authority_epoch_id=basis.authority_epoch_id,
                security_state_version=basis.version,
                requested_state=request.requested_state,
                reason_code=request.reason_code,
                checked_at=checked_at,
                restoration_allowed=True,
            ),
            basis,
            record,
            checked_at,
        )

    @staticmethod
    def _locked_basis(session: Session) -> tuple[RecoveryAuthorityBasis, SecurityStateRecord]:
        record = session.scalar(
            select(SecurityStateRecord)
            .where(SecurityStateRecord.id == 1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        require_capability(session, SecurityCapability.READ_AUDIT)
        current = SecurityStateStore(session).load()
        if record is None:
            raise ProtectedRestorationDenied("Security state is unavailable")
        origin = None
        if current.recovery_bootstrap_pending:
            if (
                record.recovery_bootstrap_from_version is None
                or record.recovery_bootstrap_started_at is None
                or record.recovery_bootstrap_from_state is None
            ):
                raise ProtectedRestorationDenied("Bootstrap origin is missing")
            origin = RecoveryBootstrapOrigin(
                state=SecurityState(record.recovery_bootstrap_from_state),
                version=record.recovery_bootstrap_from_version,
                started_at=record.recovery_bootstrap_started_at,
            )
        return (
            RecoveryAuthorityBasis(
                security_state_id=1,
                authority_epoch_id=current.authority_epoch_id.value,
                state=current.state,
                version=current.version,
                recovery_bootstrap_pending=current.recovery_bootstrap_pending,
                bootstrap_origin=origin,
            ),
            record,
        )

    @staticmethod
    def _reconcile(
        session: Session,
        context_id: UUID,
        basis: RecoveryAuthorityBasis,
        checked_at: datetime,
    ) -> RecoveryReconciliation:
        try:
            context_service = RecoveryContextService
            record = session.get(RecoveryContextRecord, context_id)
            if record is None:
                raise ProtectedRestorationDenied("Recovery context not found")
            context = RecoveryContextService.__new__(RecoveryContextService)._decode(
                session, record
            )
            context_evidence = set(context.evidence_basis)
            current_evidence, current_unresolved, partial = context_service._inventory(session)
            current_evidence_set = set(current_evidence)
            current_unresolved_set = set(current_unresolved)
            operations = RecoveryReconciliationService._operations(
                session,
                context,
                current_unresolved_set,
            )
            checks = (
                RecoveryReconciliationService._authority_lineage(
                    context,
                    basis,
                    checked_at,
                ),
                RecoveryReconciliationService._history_integrity(
                    context_evidence,
                    current_evidence_set,
                ),
                RecoveryReconciliationService._evidence_integrity(
                    context,
                    context_evidence,
                    current_evidence_set,
                    partial,
                ),
                RecoveryReconciliationService._operation_outcomes(
                    context,
                    current_unresolved_set,
                    operations,
                    partial,
                ),
                RecoveryReconciliationService._configuration_integrity(context, partial),
            )
            restoration_allowed = all(
                check.outcome is ReconciliationOutcome.PASSED for check in checks
            )
            return RecoveryReconciliation(
                context_id=context.context_id,
                incident_id=context.incident_id,
                authority_basis=basis,
                checked_at=checked_at,
                inventory_status=RecoveryInventoryStatus.PARTIAL
                if partial
                else RecoveryInventoryStatus.COMPLETE,
                checks=checks,
                operations=operations,
                restoration_allowed=restoration_allowed,
            )
        except RecoveryReconciliationConflict as exc:
            raise ProtectedRestorationDenied("Recovery reconciliation failed") from exc
