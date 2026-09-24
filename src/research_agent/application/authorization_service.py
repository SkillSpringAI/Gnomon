"""Trusted local issuance for bounded authorization artifacts."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import Engine, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from research_agent.application.security_capability import SecurityCapability, require_capability
from research_agent.application.security_state_store import SecurityStateStore
from research_agent.domain.authorization import (
    AuthorizationCapability,
    ExecutionAuthorization,
    IssueExecutionAuthorization,
    IssueOperatorAuthorization,
    OperatorAuthorization,
    validate_execution_authorization,
    validate_operator_authorization,
)
from research_agent.persistence.authorization import (
    AuthorizationAuditRecord,
    ExecutionAuthorizationRecord,
    OperatorAuthorizationRecord,
)
from research_agent.persistence.models import SecurityStateRecord

LOCAL_AUTHORIZATION_ACTOR_ID = "local-authorization-service"


class AuthorizationConflict(RuntimeError):
    """Retry unchanged after concurrency, or obtain a fresh authority epoch."""


class AuthorizationUnavailable(RuntimeError):
    """Missing or malformed authorization history is never silently repaired."""


class AuthorizationService:
    """Issue local authorization evidence without consuming it for recovery actions."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @contextmanager
    def _transaction(self) -> Iterator[Session]:
        try:
            with self.engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
                with Session(bind=conn) as session, session.begin():
                    yield session
        except IntegrityError as exc:
            raise AuthorizationConflict("Authorization persistence conflict") from exc
        except DBAPIError as exc:
            if getattr(exc.orig, "sqlstate", None) in {"40001", "40P01"}:
                raise AuthorizationConflict("Authority snapshot changed") from exc
            raise

    @staticmethod
    def _authority(session: Session) -> tuple[UUID, int]:
        record = session.scalar(
            select(SecurityStateRecord)
            .where(SecurityStateRecord.id == 1)
            .with_for_update(read=True)
        )
        require_capability(session, SecurityCapability.READ_AUDIT)
        current = SecurityStateStore(session).load()
        assert record is not None
        return current.authority_epoch_id.value, current.version

    def current_authority_epoch_id(self) -> UUID:
        with self._transaction() as session:
            epoch, _ = self._authority(session)
            return epoch

    def issue_operator(self, request: IssueOperatorAuthorization) -> OperatorAuthorization:
        request = IssueOperatorAuthorization.model_validate(request)
        command = request.model_dump(mode="json")
        with self._transaction() as session:
            epoch, version = self._authority(session)
            existing = session.get(OperatorAuthorizationRecord, request.authorization_id)
            if existing is not None:
                historical = self._decode_operator(session, existing)
                if existing.command != command:
                    raise AuthorizationConflict(
                        "Operator authorization identity was used for a different request"
                    )
                return historical
            if request.expected_authority_epoch_id != epoch:
                raise AuthorizationConflict("Expected authority epoch is stale")
            now = datetime.now(UTC)
            try:
                authorization = OperatorAuthorization(
                    authorization_id=request.authorization_id,
                    principal=request.principal,
                    granted_capability=request.granted_capability,
                    scope=request.scope,
                    authority_epoch_id=epoch,
                    issuance_basis=request.issuance_basis,
                    issued_at=now,
                    expires_at=request.expires_at,
                    replay_id=request.replay_id,
                    recovery_context_id=request.recovery_context_id,
                )
                validate_operator_authorization(
                    authorization,
                    current_authority_epoch_id=epoch,
                    now=now,
                    recovery_context_id=request.recovery_context_id,
                )
            except (ValueError, ValidationError) as exc:
                raise AuthorizationConflict("Operator authorization request is invalid") from exc
            session.add(
                OperatorAuthorizationRecord(
                    authorization_id=authorization.authorization_id,
                    authority_epoch_id=epoch,
                    security_state_version=version,
                    issued_at=authorization.issued_at,
                    expires_at=authorization.expires_at,
                    replay_id=authorization.replay_id,
                    recovery_context_id=authorization.recovery_context_id,
                    authorization=authorization.model_dump(mode="json"),
                    command=command,
                )
            )
            self._record_audit(
                session,
                artifact_id=authorization.authorization_id,
                artifact_type="operator_authorization",
                event_type="authorization.operator_issued",
                epoch=epoch,
                version=version,
                created_at=authorization.issued_at,
            )
            session.flush()
            return authorization

    def issue_execution(self, request: IssueExecutionAuthorization) -> ExecutionAuthorization:
        request = IssueExecutionAuthorization.model_validate(request)
        command = request.model_dump(mode="json")
        with self._transaction() as session:
            epoch, version = self._authority(session)
            existing = session.get(
                ExecutionAuthorizationRecord,
                request.execution_authorization_id,
            )
            if existing is not None:
                historical = self._decode_execution(session, existing)
                if existing.command != command:
                    raise AuthorizationConflict(
                        "Execution authorization identity was used for a different request"
                    )
                return historical
            if request.expected_authority_epoch_id != epoch:
                raise AuthorizationConflict("Expected authority epoch is stale")
            operator_record = session.get(
                OperatorAuthorizationRecord,
                request.operator_authorization_id,
            )
            if operator_record is None:
                raise AuthorizationUnavailable("Operator authorization not found")
            operator = self._decode_operator(session, operator_record)
            now = datetime.now(UTC)
            try:
                execution = ExecutionAuthorization(
                    execution_authorization_id=request.execution_authorization_id,
                    execution_id=request.execution_id,
                    operator_authorization_id=request.operator_authorization_id,
                    granted_capability=operator.granted_capability,
                    scope=request.scope,
                    authority_epoch_id=epoch,
                    issued_at=now,
                    expires_at=request.expires_at,
                    replay_id=request.replay_id,
                    recovery_context_id=request.recovery_context_id,
                )
                validate_execution_authorization(
                    execution,
                    operator,
                    current_authority_epoch_id=epoch,
                    now=now,
                )
            except (ValueError, ValidationError) as exc:
                raise AuthorizationConflict("Execution authorization request is invalid") from exc
            session.add(
                ExecutionAuthorizationRecord(
                    execution_authorization_id=execution.execution_authorization_id,
                    execution_id=execution.execution_id,
                    operator_authorization_id=execution.operator_authorization_id,
                    authority_epoch_id=epoch,
                    security_state_version=version,
                    issued_at=execution.issued_at,
                    expires_at=execution.expires_at,
                    replay_id=execution.replay_id,
                    recovery_context_id=execution.recovery_context_id,
                    authorization=execution.model_dump(mode="json"),
                    command=command,
                )
            )
            self._record_audit(
                session,
                artifact_id=execution.execution_authorization_id,
                artifact_type="execution_authorization",
                event_type="authorization.execution_issued",
                epoch=epoch,
                version=version,
                created_at=execution.issued_at,
            )
            session.flush()
            return execution

    def require_current_execution(
        self,
        execution_authorization_id: UUID,
        *,
        recovery_context_id: UUID | None = None,
        required_capability: AuthorizationCapability | None = None,
    ) -> ExecutionAuthorization:
        """Return execution authorization only when it is fresh for current effects."""
        with self._transaction() as session:
            epoch, _ = self._authority(session)
            execution_record = session.get(
                ExecutionAuthorizationRecord,
                execution_authorization_id,
            )
            if execution_record is None:
                raise AuthorizationUnavailable("Execution authorization not found")
            execution = self._decode_execution(session, execution_record)
            operator_record = session.get(
                OperatorAuthorizationRecord,
                execution.operator_authorization_id,
            )
            if operator_record is None:
                raise AuthorizationUnavailable("Operator authorization not found")
            operator = self._decode_operator(session, operator_record)
            try:
                validate_execution_authorization(
                    execution,
                    operator,
                    current_authority_epoch_id=epoch,
                    now=datetime.now(UTC),
                )
                if (
                    recovery_context_id is not None
                    and execution.recovery_context_id != recovery_context_id
                ):
                    raise ValueError("Execution authorization is not bound to this context")
                if (
                    required_capability is not None
                    and execution.granted_capability != required_capability
                ):
                    raise ValueError("Execution authorization lacks the required capability")
            except ValueError as exc:
                raise AuthorizationConflict("Execution authorization is not current") from exc
            return execution

    @staticmethod
    def _record_audit(
        session: Session,
        *,
        artifact_id: UUID,
        artifact_type: str,
        event_type: str,
        epoch: UUID,
        version: int,
        created_at: datetime,
    ) -> None:
        session.add(
            AuthorizationAuditRecord(
                artifact_id=artifact_id,
                artifact_type=artifact_type,
                event_type=event_type,
                actor_type="local_operator",
                actor_id=LOCAL_AUTHORIZATION_ACTOR_ID,
                authority_epoch_id=epoch,
                security_state_version=version,
                created_at=created_at,
            )
        )

    def _decode_operator(
        self,
        session: Session,
        record: OperatorAuthorizationRecord,
    ) -> OperatorAuthorization:
        try:
            authorization = OperatorAuthorization.model_validate(record.authorization)
            command = IssueOperatorAuthorization.model_validate(record.command)
            audit = session.get(AuthorizationAuditRecord, record.authorization_id)
            if (
                authorization.authorization_id != record.authorization_id
                or authorization.authority_epoch_id != record.authority_epoch_id
                or authorization.issued_at != record.issued_at
                or authorization.expires_at != record.expires_at
                or authorization.replay_id != record.replay_id
                or authorization.recovery_context_id != record.recovery_context_id
                or command.authorization_id != authorization.authorization_id
                or command.expected_authority_epoch_id != authorization.authority_epoch_id
                or command.expires_at != authorization.expires_at
                or command.replay_id != authorization.replay_id
                or command.recovery_context_id != authorization.recovery_context_id
                or audit is None
                or audit.artifact_type != "operator_authorization"
                or audit.event_type != "authorization.operator_issued"
                or audit.actor_type != "local_operator"
                or audit.actor_id != LOCAL_AUTHORIZATION_ACTOR_ID
                or audit.authority_epoch_id != record.authority_epoch_id
                or audit.security_state_version != record.security_state_version
                or audit.created_at != record.issued_at
            ):
                raise ValueError("Operator authorization record disagrees with command or audit")
            return authorization
        except (ValueError, ValidationError) as exc:
            raise AuthorizationUnavailable("Stored operator authorization is invalid") from exc

    def _decode_execution(
        self,
        session: Session,
        record: ExecutionAuthorizationRecord,
    ) -> ExecutionAuthorization:
        try:
            authorization = ExecutionAuthorization.model_validate(record.authorization)
            command = IssueExecutionAuthorization.model_validate(record.command)
            audit = session.get(AuthorizationAuditRecord, record.execution_authorization_id)
            if (
                authorization.execution_authorization_id
                != record.execution_authorization_id
                or authorization.execution_id != record.execution_id
                or authorization.operator_authorization_id != record.operator_authorization_id
                or authorization.authority_epoch_id != record.authority_epoch_id
                or authorization.issued_at != record.issued_at
                or authorization.expires_at != record.expires_at
                or authorization.replay_id != record.replay_id
                or authorization.recovery_context_id != record.recovery_context_id
                or command.execution_authorization_id
                != authorization.execution_authorization_id
                or command.execution_id != authorization.execution_id
                or command.operator_authorization_id != authorization.operator_authorization_id
                or command.expected_authority_epoch_id != authorization.authority_epoch_id
                or command.expires_at != authorization.expires_at
                or command.replay_id != authorization.replay_id
                or command.recovery_context_id != authorization.recovery_context_id
                or audit is None
                or audit.artifact_type != "execution_authorization"
                or audit.event_type != "authorization.execution_issued"
                or audit.actor_type != "local_operator"
                or audit.actor_id != LOCAL_AUTHORIZATION_ACTOR_ID
                or audit.authority_epoch_id != record.authority_epoch_id
                or audit.security_state_version != record.security_state_version
                or audit.created_at != record.issued_at
            ):
                raise ValueError("Execution authorization record disagrees with command or audit")
            return authorization
        except (ValueError, ValidationError) as exc:
            raise AuthorizationUnavailable("Stored execution authorization is invalid") from exc
