"""Supported recovery inventory reads in the caller's existing session."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_agent.domain.recovery import (
    RecoveryEvidenceKind,
    RecoveryEvidenceReference,
    RecoveryOperationKind,
    UnresolvedRecoveryOperation,
)
from research_agent.persistence.models import (
    MemoryChangeRecord,
    ReportGenerationAttemptRecord,
    ResearchCycleAttemptRecord,
    ResearchEventRecord,
    SecurityTransitionRecord,
    SourceRelationshipChangeRecord,
    StoppingDecisionChangeRecord,
)


def read_supported_recovery_inventory(
    session: Session,
) -> tuple[list[RecoveryEvidenceReference], list[UnresolvedRecoveryOperation], bool]:
    """Read bounded evidence and unresolved identities without deciding authority.

    Callers retain capability checks, transactions, locks and freshness decisions.
    """
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
