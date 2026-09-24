"""Deterministic read-only reconciliation for recovery-bootstrap state."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from research_agent.application.recovery_context_service import (
    RecoveryContextService,
    RecoveryContextUnavailable,
)
from research_agent.domain.recovery import (
    ReconciledRecoveryOperation,
    ReconciliationCheck,
    ReconciliationOutcome,
    RecoveryAuthorityBasis,
    RecoveryContext,
    RecoveryEvidenceReference,
    RecoveryInventoryStatus,
    RecoveryOperationDisposition,
    RecoveryOperationKind,
    RecoveryReconciliation,
    RecoveryReconciliationCheckResult,
    UnresolvedRecoveryOperation,
    validate_recovery_context_basis,
)
from research_agent.persistence.models import (
    ReportGenerationAttemptRecord,
    ResearchCycleAttemptRecord,
)
from research_agent.persistence.recovery import RecoveryContextRecord


class RecoveryReconciliationConflict(RuntimeError):
    """Authority changed while reconciliation was reading a trusted snapshot."""


class RecoveryReconciliationService:
    """Produce a deterministic verdict without repairing or mutating state."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self._contexts = RecoveryContextService(engine)

    @contextmanager
    def _transaction(self) -> Iterator[Session]:
        try:
            with self.engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
                with Session(bind=conn) as session, session.begin():
                    yield session
        except DBAPIError as exc:
            if getattr(exc.orig, "sqlstate", None) in {"40001", "40P01"}:
                raise RecoveryReconciliationConflict(
                    "Authority snapshot changed during reconciliation"
                ) from exc
            raise

    def reconcile(self, context_id: UUID) -> RecoveryReconciliation:
        with self._transaction() as session:
            basis = RecoveryContextService._basis(session)
            record = session.get(RecoveryContextRecord, context_id)
            if record is None:
                raise RecoveryContextUnavailable("Recovery context not found")
            context = self._contexts._decode(session, record)
            checked_at = datetime.now(UTC)
            context_evidence = set(context.evidence_basis)
            current_evidence, current_unresolved, partial = RecoveryContextService._inventory(
                session
            )
            current_evidence_set = set(current_evidence)
            current_unresolved_set = set(current_unresolved)
            operations = self._operations(session, context, current_unresolved_set)
            checks = (
                self._authority_lineage(context, basis, checked_at),
                self._history_integrity(context_evidence, current_evidence_set),
                self._evidence_integrity(
                    context,
                    context_evidence,
                    current_evidence_set,
                    partial,
                ),
                self._operation_outcomes(context, current_unresolved_set, operations, partial),
                self._configuration_integrity(context, partial),
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

    @staticmethod
    def _authority_lineage(
        context: RecoveryContext,
        basis: RecoveryAuthorityBasis,
        checked_at: datetime,
    ) -> RecoveryReconciliationCheckResult:
        try:
            validate_recovery_context_basis(context, basis, now=checked_at)
        except ValueError as exc:
            return RecoveryReconciliationCheckResult(
                check=ReconciliationCheck.AUTHORITY_LINEAGE,
                outcome=ReconciliationOutcome.FAILED,
                detail=str(exc),
            )
        return RecoveryReconciliationCheckResult(
            check=ReconciliationCheck.AUTHORITY_LINEAGE,
            outcome=ReconciliationOutcome.PASSED,
            detail="RecoveryContext authority basis is current and unexpired.",
        )

    @staticmethod
    def _history_integrity(
        context_evidence: set[RecoveryEvidenceReference],
        current_evidence: set[RecoveryEvidenceReference],
    ) -> RecoveryReconciliationCheckResult:
        missing = context_evidence - current_evidence
        if missing:
            return RecoveryReconciliationCheckResult(
                check=ReconciliationCheck.HISTORY_INTEGRITY,
                outcome=ReconciliationOutcome.FAILED,
                detail="RecoveryContext references evidence that no longer exists.",
            )
        return RecoveryReconciliationCheckResult(
            check=ReconciliationCheck.HISTORY_INTEGRITY,
            outcome=ReconciliationOutcome.PASSED,
            detail="Captured evidence references still resolve in supported history.",
        )

    @staticmethod
    def _evidence_integrity(
        context: RecoveryContext,
        context_evidence: set[RecoveryEvidenceReference],
        current_evidence: set[RecoveryEvidenceReference],
        partial: bool,
    ) -> RecoveryReconciliationCheckResult:
        if context.inventory_status is not RecoveryInventoryStatus.COMPLETE or partial:
            return RecoveryReconciliationCheckResult(
                check=ReconciliationCheck.EVIDENCE_INTEGRITY,
                outcome=ReconciliationOutcome.UNKNOWN,
                detail="Inventory is partial; supported evidence cannot be fully reconciled.",
            )
        if context_evidence != current_evidence:
            return RecoveryReconciliationCheckResult(
                check=ReconciliationCheck.EVIDENCE_INTEGRITY,
                outcome=ReconciliationOutcome.FAILED,
                detail="Supported evidence changed after RecoveryContext capture.",
            )
        return RecoveryReconciliationCheckResult(
            check=ReconciliationCheck.EVIDENCE_INTEGRITY,
            outcome=ReconciliationOutcome.PASSED,
            detail="Supported evidence inventory matches the captured context.",
        )

    @staticmethod
    def _operation_outcomes(
        context: RecoveryContext,
        current_unresolved: set[UnresolvedRecoveryOperation],
        operations: tuple[ReconciledRecoveryOperation, ...],
        partial: bool,
    ) -> RecoveryReconciliationCheckResult:
        if partial:
            return RecoveryReconciliationCheckResult(
                check=ReconciliationCheck.OPERATION_OUTCOMES,
                outcome=ReconciliationOutcome.UNKNOWN,
                detail="Inventory is partial; operation outcomes cannot be fully reconciled.",
            )
        expected = set(context.unresolved_operations)
        if current_unresolved - expected:
            return RecoveryReconciliationCheckResult(
                check=ReconciliationCheck.OPERATION_OUTCOMES,
                outcome=ReconciliationOutcome.FAILED,
                detail="New unresolved operations appeared after RecoveryContext capture.",
            )
        if any(
            operation.disposition is RecoveryOperationDisposition.UNKNOWN
            for operation in operations
        ):
            return RecoveryReconciliationCheckResult(
                check=ReconciliationCheck.OPERATION_OUTCOMES,
                outcome=ReconciliationOutcome.UNKNOWN,
                detail="At least one captured operation still has an unknown outcome.",
            )
        return RecoveryReconciliationCheckResult(
            check=ReconciliationCheck.OPERATION_OUTCOMES,
            outcome=ReconciliationOutcome.PASSED,
            detail="Captured unresolved operations now have deterministic outcomes.",
        )

    @staticmethod
    def _configuration_integrity(
        context: RecoveryContext,
        partial: bool,
    ) -> RecoveryReconciliationCheckResult:
        if partial:
            return RecoveryReconciliationCheckResult(
                check=ReconciliationCheck.CONFIGURATION_INTEGRITY,
                outcome=ReconciliationOutcome.UNKNOWN,
                detail="Configuration integrity is blocked while recovery inventory is partial.",
            )
        if context.authority_basis.security_state_id != 1:
            return RecoveryReconciliationCheckResult(
                check=ReconciliationCheck.CONFIGURATION_INTEGRITY,
                outcome=ReconciliationOutcome.FAILED,
                detail="RecoveryContext is not bound to the singleton security state.",
            )
        return RecoveryReconciliationCheckResult(
            check=ReconciliationCheck.CONFIGURATION_INTEGRITY,
            outcome=ReconciliationOutcome.PASSED,
            detail="Supported configuration boundary is bound to singleton authority state.",
        )

    @staticmethod
    def _operations(
        session: Session,
        context: RecoveryContext,
        current_unresolved: set[UnresolvedRecoveryOperation],
    ) -> tuple[ReconciledRecoveryOperation, ...]:
        identities = {
            (item.kind, item.operation_id) for item in context.unresolved_operations
        } | {(item.kind, item.operation_id) for item in current_unresolved}
        operations = [
            RecoveryReconciliationService._operation(session, kind, operation_id)
            for kind, operation_id in sorted(
                identities,
                key=lambda item: (item[0].value, item[1].hex),
            )
        ]
        return tuple(operations[:100])

    @staticmethod
    def _operation(
        session: Session,
        kind: RecoveryOperationKind,
        operation_id: UUID,
    ) -> ReconciledRecoveryOperation:
        if kind is RecoveryOperationKind.PROVIDER_ATTEMPT:
            provider_record = session.get(ReportGenerationAttemptRecord, operation_id)
            if provider_record is None:
                return ReconciledRecoveryOperation(
                    kind=kind,
                    operation_id=operation_id,
                    status="missing",
                    disposition=RecoveryOperationDisposition.DID_NOT_COMMIT,
                )
            return ReconciledRecoveryOperation(
                kind=kind,
                operation_id=operation_id,
                status=provider_record.status,
                disposition=RecoveryReconciliationService._provider_disposition(
                    provider_record.status
                ),
            )
        cycle_record = session.get(ResearchCycleAttemptRecord, operation_id)
        if cycle_record is None:
            return ReconciledRecoveryOperation(
                kind=kind,
                operation_id=operation_id,
                status="missing",
                disposition=RecoveryOperationDisposition.DID_NOT_COMMIT,
            )
        return ReconciledRecoveryOperation(
            kind=kind,
            operation_id=operation_id,
            status=cycle_record.status,
            disposition=RecoveryReconciliationService._cycle_disposition(cycle_record.status),
        )

    @staticmethod
    def _provider_disposition(status: str) -> RecoveryOperationDisposition:
        if status == "SUCCEEDED":
            return RecoveryOperationDisposition.COMMITTED
        if status == "FAILED":
            return RecoveryOperationDisposition.DID_NOT_COMMIT
        return RecoveryOperationDisposition.UNKNOWN

    @staticmethod
    def _cycle_disposition(status: str) -> RecoveryOperationDisposition:
        if status in {"COMPLETED", "FAILED", "BLOCKED", "INTERRUPTED"}:
            return RecoveryOperationDisposition.COMMITTED
        return RecoveryOperationDisposition.UNKNOWN
