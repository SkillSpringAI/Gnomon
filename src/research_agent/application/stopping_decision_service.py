"""Operator-controlled, evidence-bound investigation stopping decisions."""

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_agent.application.audit_service import AuditService
from research_agent.application.cycle_planner import review_is_current, reviewed_complete
from research_agent.application.security_capability import (
    SecurityCapability,
    require_capability,
    require_locked_capability,
)
from research_agent.application.snapshot_service import SnapshotService
from research_agent.domain.events import EventPayload, EventType
from research_agent.domain.research import (
    ClaimStatus,
    CycleStatus,
    HypothesisAssessmentStatus,
    ResearchCycle,
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
        if self.actor.actor_type != "local_operator" or not self.actor.actor_id.strip():
            raise ValueError("Invalid trusted stopping-decision actor context")

    def decide(self, task_id: UUID, request: StoppingDecisionCreate) -> StoppingDecision:
        try:
            task_record = self._lock_task(task_id)
            authority = require_locked_capability(self.session, SecurityCapability.MEMORY_MUTATION)
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
            active_attempt = (
                self.session.scalar(
                    select(ResearchCycleAttemptRecord.id).where(
                        ResearchCycleAttemptRecord.task_id == task_id,
                        ResearchCycleAttemptRecord.status == "RUNNING",
                    )
                )
                is not None
            )
            if active_attempt:
                raise StoppingDecisionConflict("An active cycle attempt must be resolved first")
            if (
                self.session.scalar(
                    select(StoppingDecisionRecord.decision_id).where(
                        StoppingDecisionRecord.task_id == task_id
                    )
                )
                is not None
            ):
                raise StoppingDecisionConflict("A stopping decision already exists")
            snapshot = SnapshotService(self.session).get(task_id)
            readiness = self._readiness_from_snapshot(
                snapshot, task_record.revision, active_attempt=active_attempt
            )
            if request.expected_evidence_fingerprint != readiness.evidence_fingerprint:
                raise StoppingDecisionConflict("Evidence changed; refresh the stopping review")
            self._validate_references(request, snapshot)
            # The input's 20-entry cap applies to operator caveats only. Keep every
            # derived warning first, then all distinct caller caveats: at most
            # 20 + len(readiness.items) + one optional runtime warning, without truncation.
            # Accepted historical decisions are never re-merged on replay/read.
            derived_limitations = [
                item.detail for item in readiness.items if item.status != "satisfied"
            ]
            if request.reason is StoppingDecisionReason.RESOURCE_LIMITED:
                derived_limitations.append(
                    "Runtime limits are operator-reported and are not system-verified."
                    if request.runtime_limit_evidence
                    else "Resource limitation was reported without runtime evidence."
                )
            limitations = list(dict.fromkeys(derived_limitations + request.limitations))
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
                objective_cycle_number=self._objective_cycle_number(request, snapshot),
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
                    command_request=self._canonical_request(request),
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
        active_attempt = (
            self.session.scalar(
                select(ResearchCycleAttemptRecord.id).where(
                    ResearchCycleAttemptRecord.task_id == task_id,
                    ResearchCycleAttemptRecord.status == "RUNNING",
                )
            )
            is not None
        )
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
        if request.objective_indices:
            cycle = StoppingDecisionService._objective_cycle(request, snapshot)
            if cycle is None:
                if not snapshot.task.cycles:
                    raise StoppingDecisionConflict("Objective references require an existing cycle")
                raise StoppingDecisionConflict("Stopping decision references an unknown cycle")
            if any(
                index >= len(cycle.objectives) or index < 0 for index in request.objective_indices
            ):
                raise StoppingDecisionConflict("Stopping decision references an unknown objective")
        elif request.objective_cycle_number is not None:
            raise StoppingDecisionConflict("Objective cycle identity requires objective references")
        review_ids = {
            review.id for cycle in snapshot.task.cycles for review in cycle.objective_reviews
        }
        if not set(request.review_ids).issubset(review_ids):
            raise StoppingDecisionConflict("Stopping decision references an unknown review")

    @staticmethod
    def _objective_cycle(
        request: StoppingDecisionCreate, snapshot: InvestigationSnapshot
    ) -> ResearchCycle | None:
        if not snapshot.task.cycles:
            return None
        if request.objective_cycle_number is None:
            # Compatibility rule for pre-032 clients: objective indices without an
            # explicit cycle refer to the latest cycle and are stored resolved.
            return snapshot.task.cycles[-1]
        return next(
            (
                cycle
                for cycle in snapshot.task.cycles
                if cycle.number == request.objective_cycle_number
            ),
            None,
        )

    @staticmethod
    def _objective_cycle_number(
        request: StoppingDecisionCreate, snapshot: InvestigationSnapshot
    ) -> int | None:
        if not request.objective_indices:
            return None
        cycle = StoppingDecisionService._objective_cycle(request, snapshot)
        assert cycle is not None
        return cycle.number

    @staticmethod
    def _readiness_from_snapshot(
        snapshot: InvestigationSnapshot,
        task_revision: int,
        *,
        active_attempt: bool = False,
    ) -> StoppingReadiness:
        outstanding: set[str] = set()
        for cycle in snapshot.task.cycles:
            outstanding.update(item.strip() for item in cycle.unresolved_objectives)
            # Planned/running work is outstanding too; an empty outcome list is
            # not proof of completion. Completed cycles retain review candidates
            # so stale or unresolved effective reviews can reopen their objectives.
            if cycle.status != CycleStatus.COMPLETED:
                outstanding.update(item.strip() for item in cycle.objectives)
            else:
                outstanding.update(review.objective.strip() for review in cycle.objective_reviews)
        unresolved = sorted(
            objective
            for objective in outstanding
            if objective and not reviewed_complete(objective, snapshot)
        )
        missing = sorted(
            row.hypothesis.label for row in snapshot.hypotheses if row.assessment is None
        )
        mixed = sorted(
            row.hypothesis.label
            for row in snapshot.hypotheses
            if row.assessment is not None and row.assessment.status.value == "mixed"
        )
        unresolved_assessments = sorted(
            row.hypothesis.label
            for row in snapshot.hypotheses
            if row.assessment is not None
            and row.assessment.status is HypothesisAssessmentStatus.UNRESOLVED
        )
        contradictory = sorted(
            (
                claim.id
                for claim in snapshot.claims
                if claim.status in {ClaimStatus.CONTESTED, ClaimStatus.CONTRADICTED}
                or any(link.support_type.value == "contradicting" for link in claim.source_links)
            ),
            key=str,
        )
        stale_reviews = sorted(
            (
                review.id
                for cycle in snapshot.task.cycles
                for review in {
                    item.objective_index: item for item in cycle.objective_reviews
                }.values()
                if not review_is_current(review, snapshot)
            ),
            key=str,
        )
        no_evidence = not snapshot.sources and not snapshot.claims
        incomplete_dependence = bool(
            snapshot.source_dependence
            and (
                snapshot.source_dependence.truncated
                or snapshot.source_dependence.invalid
                or not snapshot.source_dependence.complete
            )
        )
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
                code="unresolved_assessment",
                status="attention" if unresolved_assessments else "satisfied",
                detail=(
                    f"Unresolved assessments: {', '.join(unresolved_assessments)}."
                    if unresolved_assessments
                    else "No unresolved hypothesis assessments are recorded."
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
                code="stale_reviews",
                status="attention" if stale_reviews else "satisfied",
                detail=(
                    f"{len(stale_reviews)} objective review(s) are stale against current evidence."
                    if stale_reviews
                    else "All recorded objective reviews match current evidence."
                ),
            ),
            StoppingReadinessItem(
                code="dependence_unknown",
                status="unknown" if snapshot.sources else "satisfied",
                detail=(
                    "Source dependence is incomplete or invalid; independence is unknown."
                    if incomplete_dependence
                    else "Source independence is not established by absent relationships."
                ),
                source_ids=(
                    snapshot.source_dependence.visited_source_ids
                    if snapshot.source_dependence
                    else []
                ),
            ),
            StoppingReadinessItem(
                code="no_evidence",
                status="attention" if no_evidence else "satisfied",
                detail=(
                    "No source evidence or structured claims are recorded."
                    if no_evidence
                    else "Source evidence or structured claims are recorded."
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
            "hypotheses": [
                item.model_dump(mode="json")
                for item in sorted(snapshot.hypotheses, key=lambda item: str(item.hypothesis.id))
            ],
            "claims": [
                item.model_dump(mode="json")
                for item in sorted(snapshot.claims, key=lambda item: str(item.id))
            ],
            "sources": [
                {"id": str(item.id), "observed_at": item.observed_at.isoformat()}
                for item in sorted(snapshot.sources, key=lambda item: str(item.id))
            ],
            "dependence": snapshot.source_dependence.model_dump(mode="json")
            if snapshot.source_dependence
            else None,
            "readiness": [item.model_dump(mode="json") for item in items],
        }
        fingerprint = sha256(
            json.dumps(
                fingerprint_payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")
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
            objective_cycle_number=data.get("objective_cycle_number"),
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
            objective_cycle_number=record.objective_cycle_number,
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

    @staticmethod
    def _canonical_request(request: StoppingDecisionCreate) -> dict[str, Any]:
        # Version 1 uses model-normalized scalar fields and ordered, deduplicated
        # lists. Preserve order intentionally; future normalization changes need
        # an explicit command-version compatibility policy.
        payload = request.model_dump(mode="json", exclude={"operation_id"})
        for field in (
            "source_ids",
            "claim_ids",
            "objective_indices",
            "review_ids",
            "limitations",
            "runtime_limit_evidence",
        ):
            payload[field] = list(dict.fromkeys(payload[field]))
        return {"version": 1, "operation": "CONCLUDE", "request": payload}

    def _retry_or_conflict(
        self,
        change: StoppingDecisionChangeRecord,
        task_id: UUID,
        request: StoppingDecisionCreate,
    ) -> StoppingDecision:
        if (
            change.task_id != task_id
            or change.actor_type != self.actor.actor_type
            or change.actor_id != self.actor.actor_id
            or change.command_request is None
            or change.command_request != self._canonical_request(request)
        ):
            raise StoppingDecisionConflict("Operation identity was reused with different content")
        return StoppingDecision.model_validate(change.resulting_state)
