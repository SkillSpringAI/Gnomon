"""Internal local diagnostics: capture evidence without enabling recovery actions."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid5

from sqlalchemy import Engine, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from research_agent.application.security_capability import SecurityCapability, require_capability
from research_agent.application.security_state_store import SecurityStateStore
from research_agent.domain.recovery import (
    CaptureRecoveryContext,
    ReconciliationCheck,
    RecoveryAuthorityBasis,
    RecoveryBootstrapOrigin,
    RecoveryContext,
    RecoveryEvidenceKind,
    RecoveryEvidenceReference,
    RecoveryInventoryStatus,
    RecoveryOperationKind,
    RecoveryScope,
    UnresolvedRecoveryOperation,
    validate_recovery_context_basis,
)
from research_agent.domain.security import SecurityActor, SecurityState
from research_agent.persistence.models import (
    MemoryChangeRecord,
    ReportGenerationAttemptRecord,
    ResearchCycleAttemptRecord,
    ResearchEventRecord,
    SecurityStateRecord,
    SecurityTransitionRecord,
    SourceRelationshipChangeRecord,
    StoppingDecisionChangeRecord,
)
from research_agent.persistence.recovery import RecoveryContextAuditRecord, RecoveryContextRecord

LOCAL_ACTOR_ID = "local-recovery-diagnostics"


class RecoveryContextConflict(RuntimeError):
    """Retry unchanged after concurrency, or obtain a fresh basis for a new context."""


class RecoveryContextUnavailable(RuntimeError):
    """Missing or malformed history is never silently repaired."""


class RecoveryContextService:
    """Own transactions; callers cannot compose ordinary writes into diagnostic capture.

    This is a trusted local service, not an HTTP/model-facing authorization API.
    REPEATABLE READ fixes one inventory snapshot; the singleton SHARE lock prevents
    authority changes through commit without acquiring task locks in reverse order.
    Concurrent idempotency races fail closed and can be explicitly retried.
    """

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @contextmanager
    def _transaction(self) -> Iterator[Session]:
        try:
            with self.engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
                with Session(bind=conn) as session, session.begin():
                    yield session
        except IntegrityError as exc:
            raise RecoveryContextConflict("Context persistence conflict; retry unchanged") from exc
        except DBAPIError as exc:
            if getattr(exc.orig, "sqlstate", None) in {"40001", "40P01"}:
                raise RecoveryContextConflict(
                    "Authority snapshot changed; retry unchanged"
                ) from exc
            raise

    @staticmethod
    def _basis(session: Session) -> RecoveryAuthorityBasis:
        record = session.scalar(
            select(SecurityStateRecord)
            .where(SecurityStateRecord.id == 1)
            .with_for_update(read=True)
        )
        require_capability(session, SecurityCapability.READ_AUDIT)
        current = SecurityStateStore(session).load()
        assert record is not None  # Missing singleton was rejected by the capability guard.
        origin = None
        if current.recovery_bootstrap_pending:
            if (
                record.recovery_bootstrap_from_version is None
                or record.recovery_bootstrap_started_at is None
                or record.recovery_bootstrap_from_state is None
            ):
                raise RecoveryContextUnavailable("Bootstrap origin is missing")
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

    def current_basis(self) -> RecoveryAuthorityBasis:
        with self._transaction() as session:
            return self._basis(session)

    @staticmethod
    def _incident(basis: RecoveryAuthorityBasis) -> UUID:
        origin = basis.bootstrap_origin
        if origin is None:
            raise RecoveryContextConflict("Recovery bootstrap is not pending")
        # Deterministic identity for this bootstrap, independent of context refreshes.
        return uuid5(
            basis.authority_epoch_id,
            f"recovery:{origin.state.value}:{origin.version}:"
            f"{origin.started_at.astimezone(UTC).isoformat()}",
        )

    def capture(self, request: CaptureRecoveryContext) -> RecoveryContext:
        request = CaptureRecoveryContext.model_validate(request)
        command = request.model_dump(mode="json")
        with self._transaction() as session:
            basis = self._basis(session)
            existing = session.get(RecoveryContextRecord, request.context_id)
            if existing is not None:
                historical = self._decode(session, existing)
                if existing.command != command:
                    raise RecoveryContextConflict(
                        "Context identity was used for a different request"
                    )
                return historical  # Historical replay never renews freshness or expiry.
            if basis != request.expected_basis or not basis.recovery_bootstrap_pending:
                raise RecoveryContextConflict("Expected recovery basis is stale or not pending")
            evidence, operations, partial = self._inventory(session)
            now = datetime.now(UTC)
            if request.expires_at <= now:
                raise RecoveryContextConflict("Requested context expiry is not in the future")
            context = RecoveryContext(
                context_id=request.context_id,
                incident_id=self._incident(basis),
                authority_basis=basis,
                initiating_actor=SecurityActor.LOCAL_OPERATOR,
                initiating_actor_id=LOCAL_ACTOR_ID,
                permitted_scope=tuple(RecoveryScope),
                evidence_basis=tuple(evidence),
                required_reconciliation=tuple(ReconciliationCheck),
                unresolved_operations=tuple(operations),
                inventory_status=RecoveryInventoryStatus.PARTIAL
                if partial
                else RecoveryInventoryStatus.COMPLETE,
                created_at=now,
                expires_at=request.expires_at,
            )
            session.add(
                RecoveryContextRecord(
                    context_id=context.context_id,
                    incident_id=context.incident_id,
                    authority_epoch_id=basis.authority_epoch_id,
                    security_state_version=basis.version,
                    created_at=now,
                    expires_at=context.expires_at,
                    context=context.model_dump(mode="json"),
                    command=command,
                )
            )
            session.flush()
            self._record_audit(session, context)
            session.flush()
            return context

    @staticmethod
    def _record_audit(session: Session, context: RecoveryContext) -> None:
        session.add(
            RecoveryContextAuditRecord(
                context_id=context.context_id,
                event_type="recovery.context_recorded",
                actor_type=context.initiating_actor.value,
                actor_id=context.initiating_actor_id,
                authority_epoch_id=context.authority_basis.authority_epoch_id,
                security_state_version=context.authority_basis.version,
                created_at=context.created_at,
            )
        )

    @staticmethod
    def _inventory(
        session: Session,
    ) -> tuple[list[RecoveryEvidenceReference], list[UnresolvedRecoveryOperation], bool]:
        evidence: list[RecoveryEvidenceReference] = []
        for kind, column in (
            (RecoveryEvidenceKind.SECURITY_TRANSITION, SecurityTransitionRecord.transition_id),
            (RecoveryEvidenceKind.RESEARCH_EVENT, ResearchEventRecord.id),
            (RecoveryEvidenceKind.MEMORY_CHANGE, MemoryChangeRecord.change_id),
            (
                RecoveryEvidenceKind.SOURCE_RELATIONSHIP_CHANGE,
                SourceRelationshipChangeRecord.change_id,
            ),
            (RecoveryEvidenceKind.STOPPING_DECISION_CHANGE, StoppingDecisionChangeRecord.change_id),
        ):
            evidence.extend(
                RecoveryEvidenceReference(kind=kind, record_id=identity)
                for identity in session.scalars(select(column).order_by(column).limit(101))
            )
        operations: list[UnresolvedRecoveryOperation] = []
        for operation_kind, column, status, terminal in (
            (
                RecoveryOperationKind.PROVIDER_ATTEMPT,
                ReportGenerationAttemptRecord.operation_id,
                ReportGenerationAttemptRecord.status,
                ("SUCCEEDED", "FAILED"),
            ),
            (
                RecoveryOperationKind.CYCLE_ATTEMPT,
                ResearchCycleAttemptRecord.id,
                ResearchCycleAttemptRecord.status,
                ("COMPLETED", "FAILED", "BLOCKED", "INTERRUPTED"),
            ),
        ):
            # Unknown/unrecognized nonterminal statuses are retained conservatively.
            operations.extend(
                UnresolvedRecoveryOperation(
                    kind=operation_kind,
                    operation_id=identity,
                    outcome="unknown",
                )
                for identity in session.scalars(
                    select(column).where(status.not_in(terminal)).order_by(column).limit(101)
                )
            )
        partial = len(evidence) > 100 or len(operations) > 100
        return evidence[:100], operations[:100], partial

    def _decode(self, session: Session, record: RecoveryContextRecord) -> RecoveryContext:
        try:
            context = RecoveryContext.model_validate(record.context)
            command = CaptureRecoveryContext.model_validate(record.command)
            audit = session.get(RecoveryContextAuditRecord, record.context_id)
            if (
                context.context_id != record.context_id
                or context.incident_id != record.incident_id
                or context.incident_id != self._incident(context.authority_basis)
                or context.authority_basis.authority_epoch_id != record.authority_epoch_id
                or context.authority_basis.version != record.security_state_version
                or context.created_at != record.created_at
                or context.expires_at != record.expires_at
                or command.context_id != context.context_id
                or command.expected_basis != context.authority_basis
                or command.expires_at != context.expires_at
                or audit is None
                or audit.event_type != "recovery.context_recorded"
                or audit.actor_type != context.initiating_actor.value
                or audit.actor_id != context.initiating_actor_id
                or audit.authority_epoch_id != record.authority_epoch_id
                or audit.security_state_version != record.security_state_version
                or audit.created_at != record.created_at
            ):
                raise ValueError("Recovery context record disagrees with its command or audit")
            return context
        except ValueError as exc:
            raise RecoveryContextUnavailable("Stored recovery context is invalid") from exc

    def read(self, context_id: UUID, *, require_current: bool = False) -> RecoveryContext:
        with self._transaction() as session:
            basis = self._basis(session)
            record = session.get(RecoveryContextRecord, context_id)
            if record is None:
                raise RecoveryContextUnavailable("Recovery context not found")
            context = self._decode(session, record)
            if require_current:
                try:
                    validate_recovery_context_basis(context, basis, now=datetime.now(UTC))
                except ValueError as exc:
                    raise RecoveryContextConflict("Stored context is expired or stale") from exc
            return context
