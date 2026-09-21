"""Operator-controlled, evidence-bound investigation stopping decisions."""

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_agent.application.audit_service import AuditService
from research_agent.application.security_capability import (
    SecurityCapability,
    require_capability,
    require_locked_capability,
)
from research_agent.application.snapshot_service import SnapshotService
from research_agent.domain.events import EventPayload, EventType
from research_agent.domain.research import (
    ClaimStatus,
    StoppingDecision,
    StoppingDecisionChange,
    StoppingDecisionCreate,
    StoppingDecisionReason,
    StoppingReadiness,
    StoppingReadinessItem,
    TaskStatus,
    utc_now,
)
from research_agent.domain.snapshot import InvestigationSnapshot
from research_agent.persistence.models import (
    ResearchCycleAttemptRecord,
    ResearchTaskRecord,
    StoppingDecisionChangeRecord,
    StoppingDecisionRecord,
)


class StoppingDecisionError(RuntimeError):
    """Base stopping-decision error."""


class StoppingDecisionConflict(StoppingDecisionError):
    """The decision is stale, conflicting, or not currently permitted."""


class StoppingDecisionNotFound(StoppingDecisionError):
    """The task or stopping decision was not found."""


@dataclass(frozen=True)
class StoppingDecisionActor:
    actor_type: Literal["local_operator"] = "local_operator"
    actor_id: str = "api:local_operator"


class StoppingDecisionService:
    """Serialize conclusion decisions with the task lifecycle transition."""

    def __init__(self, session: Session, actor: StoppingDecisionActor | None = None) -> None:
        self.session = session
        self.actor = actor or StoppingDecisionActor()

    def decide(self, task_id: UUID, request: StoppingDecisionCreate) -> StoppingDecision:
        try:
            task_record = self._lock_task(task_id)
            authority = require_locked_capability(
                self.session, SecurityCapability.MEMORY_MUTATION
            )
            existing_change = self.session.scalar(
                select(StoppingDecisionChangeRecord).where(
                    StoppingDecisionChangeRecord.operation_id == request.operation_id
                )
            )
            if existing_change is not None:
                return self._retry_or_conflict(existing_change, task_id, request)
            if task_record.status != request.expected_status.value:
                raise StoppingDecisionConflict(
                    "Investigation status changed; reload before retrying"
                )
            if task_record.revision != request.expected_revision:
                raise StoppingDecisionConflict("Investigation revision is stale")
            if task_record.status not in {
                TaskStatus.ACTIVE.value,
                TaskStatus.PAUSED.value,
                TaskStatus.BLOCKED.value,
            }:
                raise StoppingDecisionConflict("Only an unfinished investigation can be concluded")
            active_attempt = self.session.scalar(
                select(ResearchCycleAttemptRecord.id).where(
                    ResearchCycleAttemptRecord.task_id == task_id,
                    ResearchCycleAttemptRecord.status == "RUNNING",
                )
            ) is not None
            if active_attempt:
                raise StoppingDecisionConflict("An active cycle attempt must be resolved first")
            if self.session.scalar(
                select(StoppingDecisionRecord.decision_id).where(
                    StoppingDecisionRecord.task_id == task_id
                )
            ) is not None:
                raise StoppingDecisionConflict("A stopping decision already exists")
            snapshot = SnapshotService(self.session).get(task_id)
            readiness = self._readiness_from_snapshot(
                snapshot, task_record.revision, active_attempt=active_attempt
            )
            if request.expected_evidence_fingerprint != readiness.evidence_fingerprint:
                raise StoppingDecisionConflict("Evidence changed; refresh the stopping review")
            self._validate_references(request, snapshot)
            limitations = list(dict.fromkeys(request.limitations + [
                item.detail for item in readiness.items if item.status != "satisfied"
            ]))[:20]
            decision_id = uuid4()
            now = utc_now()
            decision = StoppingDecision(
                decision_id=decision_id,
                task_id=task_id,
                revision=1,
                operation_id=request.operation_id,
                reason=request.reason,
                rationale=request.rationale,
                source_ids=list(dict.fromkeys(request.source_ids)),
                claim_ids=list(dict.fromkeys(request.claim_ids)),
                objective_indices=list(dict.fromkeys(request.objective_indices)),
                review_ids=list(dict.fromkeys(request.review_ids)),
                limitations=limitations,
                evidence_fingerprint=readiness.evidence_fingerprint,
                runtime_limit_evidence=list(dict.fromkeys(request.runtime_limit_evidence)),
                actor_type=self.actor.actor_type,
                actor_id=self.actor.actor_id,
                created_at=now,
            )
            self.session.add(self._record_from_decision(decision))
            self.session.flush()
            change_id = uuid4()
            self.session.add(
                StoppingDecisionChangeRecord(
                    change_id=change_id,
                    decision_id=decision_id,
                    task_id=task_id,
                    operation_id=request.operation_id,
                    previous_revision=0,
                    revision=1,
                    resulting_state=decision.model_dump(mode="json"),
                    actor_type=self.actor.actor_type,
                    actor_id=self.actor.actor_id,
                    created_at=decision.created_at,
                )
            )
            task_record.status = TaskStatus.CONCLUDED.value
            task_record.revision += 1
            task_record.updated_at = decision.created_at
            AuditService(self.session).stage(
                task_id,
                EventType.STOPPING_DECISION_RECORDED,
                EventPayload(
                    operation_id=request.operation_id,
                    stopping_decision_id=decision_id,
                    stopping_reason=request.reason.value,
                    stopping_revision=1,
                    evidence_fingerprint=decision.evidence_fingerprint,
                    authority_epoch_id=authority.authority_epoch_id.value,
                    security_state_version=authority.version,
                    actor="local_operator",
                    result="committed",
                ),
            )
            self.session.commit()
            return decision
        except Exception:
            self.session.rollback()
            raise

    def get(self, task_id: UUID) -> StoppingDecision:
        require_capability(self.session, SecurityCapability.READ_AUDIT)
        record = self.session.scalar(
            select(StoppingDecisionRecord).where(StoppingDecisionRecord.task_id == task_id)
        )
        if record is None:
            raise StoppingDecisionNotFound("Stopping decision was not found")
        return self._decision_from_record(record)

    def history(self, task_id: UUID) -> list[StoppingDecisionChange]:
        require_capability(self.session, SecurityCapability.READ_AUDIT)
        records = self.session.scalars(
            select(StoppingDecisionChangeRecord)
            .where(StoppingDecisionChangeRecord.task_id == task_id)
            .order_by(StoppingDecisionChangeRecord.revision)
        ).all()
        if not records:
            if self.session.get(ResearchTaskRecord, task_id) is None:
                raise StoppingDecisionNotFound("Investigation was not found")
            return []
        return [self._change_from_record(record) for record in records]

    def readiness(self, task_id: UUID) -> StoppingReadiness:
        require_capability(self.session, SecurityCapability.READ_AUDIT)
        task_record = self.session.get(ResearchTaskRecord, task_id)
        if task_record is None:
            raise StoppingDecisionNotFound("Investigation was not found")
        snapshot = SnapshotService(self.session).get(task_id)
        active_attempt = self.session.scalar(
            select(ResearchCycleAttemptRecord.id).where(
                ResearchCycleAttemptRecord.task_id == task_id,
                ResearchCycleAttemptRecord.status == "RUNNING",
            )
        ) is not None
        result = self._readiness_from_snapshot(
            snapshot, task_record.revision, active_attempt=active_attempt
        )
        current = self.session.scalar(
            select(StoppingDecisionRecord).where(StoppingDecisionRecord.task_id == task_id)
        )
        return result.model_copy(
            update={
                "current_decision": self._decision_from_record(current)
                if current is not None
                else None
            }
        )

    def _lock_task(self, task_id: UUID) -> ResearchTaskRecord:
        record = self.session.scalar(
            select(ResearchTaskRecord)
            .where(ResearchTaskRecord.id == task_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if record is None:
            raise StoppingDecisionNotFound("Investigation was not found")
        return record

    @staticmethod
    def _validate_references(
        request: StoppingDecisionCreate, snapshot: InvestigationSnapshot
    ) -> None:
        source_ids = {item.id for item in snapshot.sources}
        claim_ids = {item.id for item in snapshot.claims}
        if not set(request.source_ids).issubset(source_ids):
            raise StoppingDecisionConflict("Stopping decision references an unknown source")
        if not set(request.claim_ids).issubset(claim_ids):
            raise StoppingDecisionConflict("Stopping decision references an unknown claim")
        if request.objective_indices and any(
            index >= len(snapshot.task.cycles[-1].objectives) or index < 0
            for index in request.objective_indices
        ):
            raise StoppingDecisionConflict("Stopping decision references an unknown objective")
        review_ids = {
            review.id
            for cycle in snapshot.task.cycles
            for review in cycle.objective_reviews
        }
        if not set(request.review_ids).issubset(review_ids):
            raise StoppingDecisionConflict("Stopping decision references an unknown review")

    @staticmethod
    def _readiness_from_snapshot(
        snapshot: InvestigationSnapshot,
        task_revision: int,
        *,
        active_attempt: bool = False,
    ) -> StoppingReadiness:
        latest_cycle = snapshot.task.cycles[-1] if snapshot.task.cycles else None
        unresolved = latest_cycle.unresolved_objectives if latest_cycle else []
        missing = [row.hypothesis.label for row in snapshot.hypotheses if row.assessment is None]
        mixed = [
            row.hypothesis.label
            for row in snapshot.hypotheses
            if row.assessment is not None and row.assessment.status.value == "mixed"
        ]
        contradictory = [
            claim.id
            for claim in snapshot.claims
            if claim.status in {ClaimStatus.CONTESTED, ClaimStatus.CONTRADICTED}
        ]
        items = [
            StoppingReadinessItem(
                code="unresolved_objectives",
                status="attention" if unresolved else "satisfied",
                detail=(
                    f"{len(unresolved)} unresolved objective(s) remain."
                    if unresolved
                    else "No unresolved objectives are recorded."
                ),
            ),
            StoppingReadinessItem(
                code="missing_assessment",
                status="attention" if missing else "satisfied",
                detail=(
                    f"Missing assessments: {', '.join(missing)}."
                    if missing
                    else "All hypotheses have current assessments."
                ),
            ),
            StoppingReadinessItem(
                code="mixed_assessment",
                status="attention" if mixed else "satisfied",
                detail=(
                    f"Mixed assessments: {', '.join(mixed)}."
                    if mixed
                    else "No mixed hypothesis assessments are recorded."
                ),
            ),
            StoppingReadinessItem(
                code="contradictory_claims",
                status="attention" if contradictory else "satisfied",
                detail=(
                    f"{len(contradictory)} contested or contradicted claim(s) remain."
                    if contradictory
                    else "No contested or contradicted claims are recorded."
                ),
                claim_ids=contradictory,
            ),
            StoppingReadinessItem(
                code="dependence_unknown",
                status=(
                    "unknown"
                    if snapshot.source_dependence and snapshot.sources
                    else "satisfied"
                ),
                detail="Source independence is not established by absent or partial relationships.",
                source_ids=(
                    snapshot.source_dependence.visited_source_ids
                    if snapshot.source_dependence
                    else []
                ),
            ),
            StoppingReadinessItem(
                code="active_attempt",
                status="unknown" if active_attempt else "satisfied",
                detail="Active cycle attempts must be resolved before conclusion.",
            ),
        ]
        fingerprint_payload = {
            "task": snapshot.task.model_dump(
                mode="json", exclude={"status", "updated_at", "revision"}
            ),
            "hypotheses": [item.model_dump(mode="json") for item in snapshot.hypotheses],
            "claims": [item.model_dump(mode="json") for item in snapshot.claims],
            "sources": [
                {"id": str(item.id), "observed_at": item.observed_at.isoformat()}
                for item in snapshot.sources
            ],
            "dependence": snapshot.source_dependence.model_dump(mode="json")
            if snapshot.source_dependence
            else None,
            "readiness": [item.model_dump(mode="json") for item in items],
        }
        fingerprint = sha256(
            json.dumps(fingerprint_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return StoppingReadiness(
            task_id=snapshot.task.id,
            task_status=snapshot.task.status,
            task_revision=task_revision,
            evidence_fingerprint=fingerprint,
            items=items,
        )

    @staticmethod
    def _record_from_decision(decision: StoppingDecision) -> StoppingDecisionRecord:
        data = decision.model_dump(mode="json")
        return StoppingDecisionRecord(
            decision_id=decision.decision_id,
            task_id=decision.task_id,
            revision=decision.revision,
            operation_id=decision.operation_id,
            reason=decision.reason.value,
            rationale=decision.rationale,
            source_ids=data["source_ids"],
            claim_ids=data["claim_ids"],
            objective_indices=data["objective_indices"],
            review_ids=data["review_ids"],
            limitations=data["limitations"],
            evidence_fingerprint=decision.evidence_fingerprint,
            runtime_limit_evidence=data["runtime_limit_evidence"],
            actor_type=decision.actor_type,
            actor_id=decision.actor_id,
            created_at=decision.created_at,
        )

    @staticmethod
    def _decision_from_record(record: StoppingDecisionRecord) -> StoppingDecision:
        return StoppingDecision(
            decision_id=record.decision_id,
            task_id=record.task_id,
            revision=record.revision,
            operation_id=record.operation_id,
            reason=StoppingDecisionReason(record.reason),
            rationale=record.rationale,
            source_ids=[UUID(item) for item in record.source_ids],
            claim_ids=[UUID(item) for item in record.claim_ids],
            objective_indices=record.objective_indices,
            review_ids=[UUID(item) for item in record.review_ids],
            limitations=record.limitations,
            evidence_fingerprint=record.evidence_fingerprint,
            runtime_limit_evidence=record.runtime_limit_evidence,
            actor_type=cast(Literal["local_operator"], record.actor_type),
            actor_id=record.actor_id,
            created_at=record.created_at,
        )

    @classmethod
    def _change_from_record(cls, record: StoppingDecisionChangeRecord) -> StoppingDecisionChange:
        return StoppingDecisionChange(
            change_id=record.change_id,
            decision_id=record.decision_id,
            task_id=record.task_id,
            operation_id=record.operation_id,
            previous_revision=record.previous_revision,
            revision=record.revision,
            resulting_state=StoppingDecision.model_validate(record.resulting_state),
            actor_type=cast(Literal["local_operator"], record.actor_type),
            actor_id=record.actor_id,
            created_at=record.created_at,
        )

    def _retry_or_conflict(
        self,
        change: StoppingDecisionChangeRecord,
        task_id: UUID,
        request: StoppingDecisionCreate,
    ) -> StoppingDecision:
        state = change.resulting_state
        expected = {
            "reason": request.reason.value,
            "rationale": request.rationale,
            "source_ids": [str(item) for item in dict.fromkeys(request.source_ids)],
            "claim_ids": [str(item) for item in dict.fromkeys(request.claim_ids)],
            "objective_indices": list(dict.fromkeys(request.objective_indices)),
            "review_ids": [str(item) for item in dict.fromkeys(request.review_ids)],
            "limitations": list(dict.fromkeys(request.limitations)),
            "runtime_limit_evidence": list(dict.fromkeys(request.runtime_limit_evidence)),
            "evidence_fingerprint": request.expected_evidence_fingerprint,
        }
        if (
            change.task_id != task_id
            or any(state.get(key) != value for key, value in expected.items())
        ):
            raise StoppingDecisionConflict("Operation identity was reused with different content")
        return StoppingDecision.model_validate(state)
