"""Bounded recovery evidence contracts; none of these values grants authority."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from research_agent.domain.security import SecurityActor, SecurityReasonCode, SecurityState


def _non_nil(value: UUID) -> UUID:
    if value.int == 0:
        raise ValueError("Recovery identifiers must not be nil")
    return value


RecoveryId = Annotated[UUID, AfterValidator(_non_nil)]
StateVersion = Annotated[int, Field(strict=True, ge=1)]


class RecoveryValue(BaseModel):
    """Frozen nested values and tuple collections prevent accidental in-place edits."""

    model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="always")


class RecoveryBootstrapOrigin(RecoveryValue):
    state: SecurityState
    version: StateVersion
    started_at: AwareDatetime


class RecoveryAuthorityBasis(RecoveryValue):
    """Effective singleton authority snapshot, supplied by a trusted future loader."""

    security_state_id: Literal[1]
    authority_epoch_id: RecoveryId
    state: SecurityState
    version: StateVersion
    recovery_bootstrap_pending: Annotated[bool, Field(strict=True)]
    bootstrap_origin: RecoveryBootstrapOrigin | None

    @model_validator(mode="after")
    def consistent_bootstrap(self) -> Self:
        if self.recovery_bootstrap_pending:
            if (
                self.state is not SecurityState.RECOVERY_REQUIRED
                or self.bootstrap_origin is None
                or self.version <= self.bootstrap_origin.version
            ):
                raise ValueError("Pending bootstrap requires restrictive state and older origin")
        elif self.bootstrap_origin is not None:
            raise ValueError("Non-pending authority cannot retain bootstrap origin metadata")
        return self


class RecoveryScope(StrEnum):
    """Evidence inspection scope ceiling, not a permission or restoration action."""

    AUTHORITY = "inspect_authority"
    HISTORY = "inspect_history"
    OPERATIONS = "inventory_operations"


class ReconciliationCheck(StrEnum):
    AUTHORITY_LINEAGE = "authority_lineage"
    HISTORY_INTEGRITY = "history_integrity"
    EVIDENCE_INTEGRITY = "evidence_integrity"
    OPERATION_OUTCOMES = "operation_outcomes"
    CONFIGURATION_INTEGRITY = "configuration_integrity"


class ReconciliationOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class RecoveryInventoryStatus(StrEnum):
    NOT_COLLECTED = "not_collected"
    PARTIAL = "partial"
    COMPLETE = "complete"


class RecoveryEvidenceKind(StrEnum):
    SECURITY_TRANSITION = "security_transition"
    RESEARCH_EVENT = "research_event"
    MEMORY_CHANGE = "memory_change"
    SOURCE_RELATIONSHIP_CHANGE = "source_relationship_change"
    STOPPING_DECISION_CHANGE = "stopping_decision_change"


class RecoveryEvidenceReference(RecoveryValue):
    """Identity only: no credentials, source content, or free-form evidence payload."""

    kind: RecoveryEvidenceKind
    record_id: RecoveryId


class RecoveryOperationKind(StrEnum):
    PROVIDER_ATTEMPT = "provider_attempt"
    CYCLE_ATTEMPT = "cycle_attempt"


class UnresolvedRecoveryOperation(RecoveryValue):
    kind: RecoveryOperationKind
    operation_id: RecoveryId
    outcome: Literal["unknown", "unresolved"]


class RecoveryOperationDisposition(StrEnum):
    COMMITTED = "committed"
    DID_NOT_COMMIT = "did_not_commit"
    UNKNOWN = "unknown"


class ReconciledRecoveryOperation(RecoveryValue):
    kind: RecoveryOperationKind
    operation_id: RecoveryId
    status: Annotated[str, Field(strict=True, min_length=1, max_length=64)]
    disposition: RecoveryOperationDisposition


class RecoveryReconciliationCheckResult(RecoveryValue):
    check: ReconciliationCheck
    outcome: ReconciliationOutcome
    detail: Annotated[str, Field(strict=True, min_length=1, max_length=300)]


class RecoveryContext(RecoveryValue):
    """Immutable bootstrap-recovery evidence snapshot, with explicit incomplete inventory."""

    schema_version: Literal[1] = 1
    context_id: RecoveryId
    incident_id: RecoveryId
    authority_basis: RecoveryAuthorityBasis
    initiating_actor: SecurityActor
    initiating_actor_id: Annotated[str, Field(strict=True, min_length=1, max_length=100)]
    permitted_scope: tuple[RecoveryScope, ...] = Field(min_length=1, max_length=3)
    evidence_basis: tuple[RecoveryEvidenceReference, ...] = Field(max_length=100)
    required_reconciliation: tuple[ReconciliationCheck, ...] = Field(min_length=5, max_length=5)
    unresolved_operations: tuple[UnresolvedRecoveryOperation, ...] = Field(max_length=100)
    inventory_status: RecoveryInventoryStatus
    created_at: AwareDatetime
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def consistent_context(self) -> Self:
        origin = self.authority_basis.bootstrap_origin
        if not self.authority_basis.recovery_bootstrap_pending or origin is None:
            raise ValueError("This context contract requires pending recovery bootstrap")
        if self.created_at < origin.started_at or self.expires_at <= self.created_at:
            raise ValueError("Context validity must follow bootstrap and have a finite end")
        if not self.initiating_actor_id.strip():
            raise ValueError("Initiating actor identity must not be blank")
        if len(set(self.permitted_scope)) != len(self.permitted_scope):
            raise ValueError("Recovery scopes must be unique")
        if set(self.required_reconciliation) != set(ReconciliationCheck):
            raise ValueError("All baseline reconciliation checks must remain required")
        evidence_ids = [(item.kind, item.record_id) for item in self.evidence_basis]
        operation_ids = [(item.kind, item.operation_id) for item in self.unresolved_operations]
        if len(set(evidence_ids)) != len(evidence_ids) or len(set(operation_ids)) != len(
            operation_ids
        ):
            raise ValueError("Recovery references must not repeat identities")
        if self.inventory_status is RecoveryInventoryStatus.NOT_COLLECTED and (
            self.evidence_basis or self.unresolved_operations
        ):
            raise ValueError("Uncollected inventory cannot contain collected references")
        return self


class CaptureRecoveryContext(RecoveryValue):
    """Trusted local command; evidence and actor attribution are never caller supplied."""

    context_id: RecoveryId
    expected_basis: RecoveryAuthorityBasis
    expires_at: AwareDatetime


class RecoveryReconciliation(RecoveryValue):
    """Read-only M1.4 verdict; this does not clear fences or restore authority."""

    schema_version: Literal[1] = 1
    context_id: RecoveryId
    incident_id: RecoveryId
    authority_basis: RecoveryAuthorityBasis
    checked_at: AwareDatetime
    inventory_status: RecoveryInventoryStatus
    checks: tuple[RecoveryReconciliationCheckResult, ...] = Field(min_length=5, max_length=5)
    operations: tuple[ReconciledRecoveryOperation, ...] = Field(max_length=100)
    restoration_allowed: Annotated[bool, Field(strict=True)]

    @model_validator(mode="after")
    def consistent_reconciliation(self) -> Self:
        if {item.check for item in self.checks} != set(ReconciliationCheck):
            raise ValueError("All reconciliation checks must be represented exactly once")
        if self.restoration_allowed and any(
            item.outcome is not ReconciliationOutcome.PASSED for item in self.checks
        ):
            raise ValueError("Restoration can be allowed only when every check passes")
        return self


class PrepareProtectedRestoration(RecoveryValue):
    """M1.5 pass-1 command; validation only, no authority transition."""

    restoration_id: RecoveryId
    context_id: RecoveryId
    operator_authorization_id: RecoveryId
    execution_authorization_id: RecoveryId
    expected_authority_epoch_id: RecoveryId
    expected_security_state_version: StateVersion
    requested_state: SecurityState
    reason_code: SecurityReasonCode

    @model_validator(mode="after")
    def bounded_restoration_request(self) -> Self:
        if self.requested_state is not SecurityState.NORMAL:
            raise ValueError("First-pass protected restoration only prepares NORMAL restoration")
        if self.reason_code is not SecurityReasonCode.RECOVERY_VERIFIED:
            raise ValueError("NORMAL restoration preparation requires RECOVERY_VERIFIED")
        return self


class PreparedProtectedRestoration(RecoveryValue):
    """Read-only evidence that pass-1 restoration preconditions held in one transaction."""

    schema_version: Literal[1] = 1
    restoration_id: RecoveryId
    context_id: RecoveryId
    incident_id: RecoveryId
    operator_authorization_id: RecoveryId
    execution_authorization_id: RecoveryId
    authority_epoch_id: RecoveryId
    security_state_version: StateVersion
    requested_state: SecurityState
    reason_code: SecurityReasonCode
    checked_at: AwareDatetime
    restoration_allowed: Literal[True]


class ProtectedRestorationResult(RecoveryValue):
    """Actual protected restoration transition result."""

    schema_version: Literal[1] = 1
    restoration_id: RecoveryId
    context_id: RecoveryId
    incident_id: RecoveryId
    transition_id: RecoveryId
    state: SecurityState
    version: StateVersion
    authority_epoch_id: RecoveryId
    completed_at: AwareDatetime


class ReplaceAuthorityEpoch(RecoveryValue):
    """M1.6 command for creating a new post-restoration authority lineage."""

    replacement_id: RecoveryId
    restoration_id: RecoveryId
    restoration_transition_id: RecoveryId
    expected_current_epoch_id: RecoveryId
    expected_security_state_version: StateVersion
    new_authority_epoch_id: RecoveryId
    reason_code: SecurityReasonCode

    @model_validator(mode="after")
    def bounded_replacement_request(self) -> Self:
        if self.new_authority_epoch_id == self.expected_current_epoch_id:
            raise ValueError("Replacement authority epoch must be new")
        if self.reason_code is not SecurityReasonCode.RECOVERY_VERIFIED:
            raise ValueError("Authority epoch replacement requires RECOVERY_VERIFIED")
        return self


class AuthorityEpochReplacementResult(RecoveryValue):
    """Evidence of a completed authority epoch replacement."""

    schema_version: Literal[1] = 1
    replacement_id: RecoveryId
    restoration_id: RecoveryId
    transition_id: RecoveryId
    previous_authority_epoch_id: RecoveryId
    authority_epoch_id: RecoveryId
    version: StateVersion
    replaced_at: AwareDatetime


def validate_recovery_context_basis(
    context: RecoveryContext, current: RecoveryAuthorityBasis, *, now: datetime
) -> None:
    """Check structure, time and snapshot equality only; never authorize an action.

    The current basis and clock must come from trusted runtime state. This pure
    function acquires no lock, proves no reference exists and performs no repair.
    A future consumer must independently authorize and recheck under its transaction.
    """
    context = RecoveryContext.model_validate(context)
    current = RecoveryAuthorityBasis.model_validate(current)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Recovery validation requires an aware clock")
    if not context.created_at <= now < context.expires_at:
        raise ValueError("Recovery context is not currently valid")
    if context.authority_basis != current:
        raise ValueError("Recovery context authority basis is stale")
