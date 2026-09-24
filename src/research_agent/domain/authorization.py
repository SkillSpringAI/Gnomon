"""Bounded operator and execution authorization evidence.

Possession of these artifacts is not enough to perform an effect. Callers must
still load current authority from trusted runtime state and recheck capability at
the point of effect.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, model_validator


def _non_nil(value: UUID) -> UUID:
    if value.int == 0:
        raise ValueError("Authorization identifiers must not be nil")
    return value


AuthorizationId = Annotated[UUID, AfterValidator(_non_nil)]


class AuthorizationValue(BaseModel):
    """Frozen nested values prevent accidental in-place mutation."""

    model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="always")


class AuthorizationCapability(StrEnum):
    """Authority-bearing capabilities that may be granted explicitly."""

    RECOVERY_ACTION = "recovery_action"
    AUTHORITY_ADMINISTRATION = "authority_administration"


class AuthorizationScopeKind(StrEnum):
    RECOVERY_CONTEXT = "recovery_context"
    SECURITY_STATE = "security_state"
    TASK = "task"


class AuthorizationScopeItem(AuthorizationValue):
    kind: AuthorizationScopeKind
    target_id: AuthorizationId | None = None

    @model_validator(mode="after")
    def bounded_identity(self) -> Self:
        if self.kind is not AuthorizationScopeKind.SECURITY_STATE and self.target_id is None:
            raise ValueError("Scoped authorizations must identify their non-singleton target")
        if self.kind is AuthorizationScopeKind.SECURITY_STATE and self.target_id is not None:
            raise ValueError("Security-state authorization is scoped to the singleton")
        return self


class OperatorPrincipalKind(StrEnum):
    LOCAL_OPERATOR = "local_operator"
    AUTHENTICATED_PRINCIPAL = "authenticated_principal"


class OperatorPrincipal(AuthorizationValue):
    kind: OperatorPrincipalKind
    principal_id: Annotated[str, Field(strict=True, min_length=1, max_length=200)]

    @model_validator(mode="after")
    def nonblank_identity(self) -> Self:
        if not self.principal_id.strip():
            raise ValueError("Principal identity must not be blank")
        return self


class AuthorizationBasisKind(StrEnum):
    RECOVERY_CONTEXT = "recovery_context"
    SECURITY_TRANSITION = "security_transition"
    OPERATOR_COMMAND = "operator_command"


class AuthorizationBasisReference(AuthorizationValue):
    kind: AuthorizationBasisKind
    record_id: AuthorizationId


class OperatorAuthorization(AuthorizationValue):
    """A bounded grant issued to an operator identity, not an authentication token."""

    schema_version: Literal[1] = 1
    authorization_id: AuthorizationId
    principal: OperatorPrincipal
    granted_capability: AuthorizationCapability
    scope: tuple[AuthorizationScopeItem, ...] = Field(min_length=1, max_length=10)
    authority_epoch_id: AuthorizationId
    issuance_basis: tuple[AuthorizationBasisReference, ...] = Field(min_length=1, max_length=20)
    issued_at: AwareDatetime
    expires_at: AwareDatetime
    replay_id: AuthorizationId
    recovery_context_id: AuthorizationId | None = None

    @model_validator(mode="after")
    def consistent_authorization(self) -> Self:
        if self.expires_at <= self.issued_at:
            raise ValueError("Authorization expiry must be after issuance")
        if len(set(self.scope)) != len(self.scope):
            raise ValueError("Authorization scope entries must be unique")
        basis_ids = [(item.kind, item.record_id) for item in self.issuance_basis]
        if len(set(basis_ids)) != len(basis_ids):
            raise ValueError("Authorization basis references must be unique")
        if self.recovery_context_id is not None:
            expected = AuthorizationScopeItem(
                kind=AuthorizationScopeKind.RECOVERY_CONTEXT,
                target_id=self.recovery_context_id,
            )
            if expected not in self.scope:
                raise ValueError("Recovery-context binding must be inside the authorization scope")
            if not any(
                item.kind is AuthorizationBasisKind.RECOVERY_CONTEXT
                and item.record_id == self.recovery_context_id
                for item in self.issuance_basis
            ):
                raise ValueError("Recovery-context binding must be part of the issuance basis")
        return self


class IssueOperatorAuthorization(AuthorizationValue):
    """Trusted issuance command; epoch and issuance time are service supplied."""

    authorization_id: AuthorizationId
    expected_authority_epoch_id: AuthorizationId
    principal: OperatorPrincipal
    granted_capability: AuthorizationCapability
    scope: tuple[AuthorizationScopeItem, ...] = Field(min_length=1, max_length=10)
    issuance_basis: tuple[AuthorizationBasisReference, ...] = Field(min_length=1, max_length=20)
    expires_at: AwareDatetime
    replay_id: AuthorizationId
    recovery_context_id: AuthorizationId | None = None


class ExecutionAuthorization(AuthorizationValue):
    """Epoch-bound authorization for one bounded execution attempt."""

    schema_version: Literal[1] = 1
    execution_authorization_id: AuthorizationId
    execution_id: AuthorizationId
    operator_authorization_id: AuthorizationId
    granted_capability: AuthorizationCapability
    scope: tuple[AuthorizationScopeItem, ...] = Field(min_length=1, max_length=10)
    authority_epoch_id: AuthorizationId
    issued_at: AwareDatetime
    expires_at: AwareDatetime
    replay_id: AuthorizationId
    recovery_context_id: AuthorizationId | None = None

    @model_validator(mode="after")
    def consistent_authorization(self) -> Self:
        if self.expires_at <= self.issued_at:
            raise ValueError("Execution authorization expiry must be after issuance")
        if len(set(self.scope)) != len(self.scope):
            raise ValueError("Execution authorization scope entries must be unique")
        if self.recovery_context_id is not None:
            expected = AuthorizationScopeItem(
                kind=AuthorizationScopeKind.RECOVERY_CONTEXT,
                target_id=self.recovery_context_id,
            )
            if expected not in self.scope:
                raise ValueError("Recovery-context binding must be inside the execution scope")
        return self


class IssueExecutionAuthorization(AuthorizationValue):
    """Trusted execution issuance command bound to an operator authorization."""

    execution_authorization_id: AuthorizationId
    expected_authority_epoch_id: AuthorizationId
    execution_id: AuthorizationId
    operator_authorization_id: AuthorizationId
    scope: tuple[AuthorizationScopeItem, ...] = Field(min_length=1, max_length=10)
    expires_at: AwareDatetime
    replay_id: AuthorizationId
    recovery_context_id: AuthorizationId | None = None


def validate_operator_authorization(
    authorization: OperatorAuthorization,
    *,
    current_authority_epoch_id: UUID,
    now: datetime,
    recovery_context_id: UUID | None = None,
) -> None:
    """Validate freshness and epoch binding only; this grants no effect."""
    authorization = OperatorAuthorization.model_validate(authorization)
    current = _non_nil(current_authority_epoch_id)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Authorization validation requires an aware clock")
    if authorization.authority_epoch_id != current:
        raise ValueError("Operator authorization authority epoch is stale")
    if not authorization.issued_at <= now < authorization.expires_at:
        raise ValueError("Operator authorization is not currently valid")
    if recovery_context_id is not None and authorization.recovery_context_id != _non_nil(
        recovery_context_id
    ):
        raise ValueError("Operator authorization is not bound to this recovery context")


def validate_execution_authorization(
    execution: ExecutionAuthorization,
    operator: OperatorAuthorization,
    *,
    current_authority_epoch_id: UUID,
    now: datetime,
) -> None:
    """Validate execution authorization without authorizing the downstream effect."""
    execution = ExecutionAuthorization.model_validate(execution)
    operator = OperatorAuthorization.model_validate(operator)
    validate_operator_authorization(
        operator,
        current_authority_epoch_id=current_authority_epoch_id,
        now=now,
        recovery_context_id=execution.recovery_context_id,
    )
    if execution.authority_epoch_id != operator.authority_epoch_id:
        raise ValueError("Execution authorization authority epoch is stale")
    if execution.operator_authorization_id != operator.authorization_id:
        raise ValueError("Execution authorization is not bound to the operator authorization")
    if execution.granted_capability != operator.granted_capability:
        raise ValueError("Execution authorization changes the granted capability")
    if not set(execution.scope).issubset(set(operator.scope)):
        raise ValueError("Execution authorization expands operator scope")
    if execution.issued_at < operator.issued_at or execution.expires_at > operator.expires_at:
        raise ValueError("Execution authorization validity exceeds operator authorization")
    if not execution.issued_at <= now < execution.expires_at:
        raise ValueError("Execution authorization is not currently valid")
