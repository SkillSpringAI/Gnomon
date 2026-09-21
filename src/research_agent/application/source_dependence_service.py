"""Governed, bounded source-dependence relationships."""

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from research_agent.application.audit_service import AuditService
from research_agent.application.security_capability import (
    SecurityCapability,
    require_capability,
    require_locked_capability,
)
from research_agent.application.security_state_store import PersistedSecurityState
from research_agent.domain.events import EventPayload, EventType
from research_agent.domain.research import (
    SourceDependenceKind,
    SourceDependenceLimits,
    SourceDependenceProjection,
    SourceRelationship,
    SourceRelationshipChange,
    SourceRelationshipCreate,
    SourceRelationshipLifecycle,
    SourceRelationshipMutation,
    SourceRelationshipReversal,
)
from research_agent.persistence.models import (
    ResearchSourceRecord,
    ResearchTaskRecord,
    SourceRelationshipChangeRecord,
    SourceRelationshipRecord,
)


class SourceDependenceError(RuntimeError):
    """Base error for bounded source-dependence operations."""


class SourceDependenceConflict(SourceDependenceError):
    """The requested relationship operation cannot be accepted."""


class SourceDependenceNotFound(SourceDependenceError):
    """A task or relationship was not found."""


@dataclass(frozen=True)
class SourceDependenceActor:
    actor_type: Literal["local_operator"] = "local_operator"
    actor_id: str = "api:local_operator"


class SourceDependenceService:
    """Serialize task-local relationship mutations and bound graph reads."""

    LIMITS = SourceDependenceLimits()

    def __init__(self, session: Session, actor: SourceDependenceActor | None = None) -> None:
        self.session = session
        self.actor = actor or SourceDependenceActor()
        if self.actor.actor_type != "local_operator" or not self.actor.actor_id.strip():
            raise ValueError("Invalid source-dependence actor context")

    def create(self, task_id: UUID, request: SourceRelationshipCreate) -> SourceRelationship:
        try:
            self._lock_task(task_id)
            authority = require_locked_capability(
                self.session, SecurityCapability.MEMORY_MUTATION
            )
            derived_id, upstream_id, low_id, high_id, direction = self._normalize_create(
                task_id, request
            )
            existing_change = self._operation_change(request.operation_id)
            if existing_change is not None:
                return self._retry_or_conflict(
                    existing_change,
                    task_id=task_id,
                    relationship_id=None,
                    kind=request.kind.value,
                    direction=direction,
                    lifecycle="active",
                    source_low_id=low_id,
                    source_high_id=high_id,
                )
            self._validate_sources(task_id, low_id, high_id)
            if request.kind is SourceDependenceKind.DERIVED_FROM:
                self._validate_no_cycle(task_id, derived_id, upstream_id)
            current = self.session.scalar(
                select(SourceRelationshipRecord)
                .where(
                    SourceRelationshipRecord.task_id == task_id,
                    SourceRelationshipRecord.source_low_id == low_id,
                    SourceRelationshipRecord.source_high_id == high_id,
                    SourceRelationshipRecord.kind == request.kind.value,
                )
                .with_for_update()
            )
            if current is not None:
                raise SourceDependenceConflict("Source relationship already exists")
            relationship_id = uuid4()
            change_id = uuid4()
            now = datetime.now(UTC)
            state = self._state(
                relationship_id=relationship_id,
                task_id=task_id,
                low_id=low_id,
                high_id=high_id,
                kind=request.kind.value,
                direction=direction,
                lifecycle="active",
                revision=1,
                latest_change_id=change_id,
                updated_at=now,
            )
            self.session.add(self._record_from_state(state))
            # The history row has a composite FK to the current projection;
            # flush the projection before inserting its first immutable change.
            self.session.flush()
            self.session.add(
                self._change_record(
                    change_id=change_id,
                    operation_id=request.operation_id,
                    state=state,
                    previous_state=None,
                    previous_revision=0,
                    operation="CREATE",
                    reason=request.reason,
                    authority=authority,
                )
            )
            self._stage_audit(task_id, request.operation_id, state)
            self.session.commit()
            return state
        except Exception:
            self.session.rollback()
            raise

    def mutate(self, task_id: UUID, request: SourceRelationshipMutation) -> SourceRelationship:
        try:
            self._lock_task(task_id)
            authority = require_locked_capability(
                self.session, SecurityCapability.MEMORY_MUTATION
            )
            current = self._relationship_for_update(task_id, request.relationship_id)
            existing_change = self._operation_change(request.operation_id)
            if existing_change is not None:
                return self._retry_or_conflict(
                    existing_change,
                    task_id=task_id,
                    relationship_id=request.relationship_id,
                    kind=current.kind,
                    direction=request.direction or current.direction,
                    lifecycle=(
                        request.lifecycle.value
                        if request.operation == "SET" and request.lifecycle
                        else "retracted"
                    ),
                )
            if current.revision != request.expected_revision:
                raise SourceDependenceConflict("Source relationship revision is stale")
            if request.operation == "RETRACT":
                lifecycle = "retracted"
                direction = current.direction
            else:
                lifecycle = (request.lifecycle or SourceRelationshipLifecycle.ACTIVE).value
                direction = request.direction or current.direction
            self._validate_direction(current.kind, direction)
            if lifecycle == "active" and current.kind == SourceDependenceKind.DERIVED_FROM.value:
                derived_id, upstream_id = self._directional_endpoints(current, direction)
                self._validate_no_cycle(task_id, derived_id, upstream_id, current.relationship_id)
            if lifecycle == current.lifecycle and direction == current.direction:
                raise SourceDependenceConflict("Source relationship mutation changes no state")
            return self._commit_change(
                task_id,
                current,
                lifecycle=lifecycle,
                direction=direction,
                operation=request.operation,
                operation_id=request.operation_id,
                reason=request.reason,
                authority=authority,
            )
        except Exception:
            self.session.rollback()
            raise

    def reverse(self, task_id: UUID, request: SourceRelationshipReversal) -> SourceRelationship:
        try:
            self._lock_task(task_id)
            authority = require_locked_capability(
                self.session, SecurityCapability.MEMORY_MUTATION
            )
            current = self._relationship_for_update(task_id, request.relationship_id)
            existing_change = self._operation_change(request.operation_id)
            if existing_change is not None:
                return self._retry_or_conflict(
                    existing_change,
                    task_id=task_id,
                    relationship_id=request.relationship_id,
                    kind=current.kind,
                    direction=current.direction,
                    lifecycle=current.lifecycle,
                )
            target = self.session.scalar(
                select(SourceRelationshipChangeRecord).where(
                    SourceRelationshipChangeRecord.change_id == request.change_id,
                    SourceRelationshipChangeRecord.relationship_id == request.relationship_id,
                    SourceRelationshipChangeRecord.task_id == task_id,
                )
            )
            if target is None:
                raise SourceDependenceNotFound("Source relationship change was not found")
            if target.operation == "REVERSE":
                raise SourceDependenceConflict("A reversal cannot reverse another reversal")
            if target.created_at < datetime.now(UTC) - timedelta(hours=48):
                raise SourceDependenceConflict("Source relationship reversal window expired")
            if current.revision != request.expected_revision or target.revision != current.revision:
                raise SourceDependenceConflict("Source relationship reversal is stale")
            previous = self._state_from_record(current)
            if target.previous_state is None:
                lifecycle = "retracted"
                direction = current.direction
            else:
                lifecycle = str(target.previous_state["lifecycle"])
                direction = str(target.previous_state["direction"])
            if lifecycle == "active" and current.kind == SourceDependenceKind.DERIVED_FROM.value:
                derived_id, upstream_id = self._directional_endpoints(current, direction)
                self._validate_no_cycle(task_id, derived_id, upstream_id, current.relationship_id)
            return self._commit_change(
                task_id,
                current,
                lifecycle=lifecycle,
                direction=direction,
                operation="REVERSE",
                operation_id=request.operation_id,
                reason=request.reason,
                authority=authority,
                reverses_change_id=target.change_id,
                previous_state_override=previous,
            )
        except Exception:
            self.session.rollback()
            raise

    def get(self, task_id: UUID, relationship_id: UUID) -> SourceRelationship:
        require_capability(self.session, SecurityCapability.READ_AUDIT)
        record = self.session.scalar(
            select(SourceRelationshipRecord).where(
                SourceRelationshipRecord.task_id == task_id,
                SourceRelationshipRecord.relationship_id == relationship_id,
            )
        )
        if record is None:
            raise SourceDependenceNotFound("Source relationship was not found")
        return self._state_from_record(record)

    def history(self, task_id: UUID, relationship_id: UUID) -> list[SourceRelationshipChange]:
        require_capability(self.session, SecurityCapability.READ_AUDIT)
        if self.session.scalar(
            select(SourceRelationshipRecord.relationship_id).where(
                SourceRelationshipRecord.task_id == task_id,
                SourceRelationshipRecord.relationship_id == relationship_id,
            )
        ) is None:
            raise SourceDependenceNotFound("Source relationship was not found")
        records = self.session.scalars(
            select(SourceRelationshipChangeRecord)
            .where(
                SourceRelationshipChangeRecord.task_id == task_id,
                SourceRelationshipChangeRecord.relationship_id == relationship_id,
            )
            .order_by(SourceRelationshipChangeRecord.revision)
        )
        return [self._change_from_record(record) for record in records]

    def project(
        self, task_id: UUID, root_source_ids: list[UUID]
    ) -> SourceDependenceProjection:
        require_capability(self.session, SecurityCapability.READ_AUDIT)
        roots = sorted(set(root_source_ids), key=lambda item: item.int)
        if len(roots) > self.LIMITS.max_roots:
            raise SourceDependenceConflict("Source dependence root limit exceeded")
        self._validate_sources(task_id, *roots)
        visited = set(roots)
        depths = {item: 0 for item in roots}
        queue = deque(roots)
        examined: dict[UUID, SourceRelationshipRecord] = {}
        frontier: set[UUID] = set()
        overflow: Literal["node_limit", "edge_limit", "depth_limit"] | None = None
        while queue and overflow is None:
            source_id = queue.popleft()
            depth = depths[source_id]
            records = self.session.scalars(
                select(SourceRelationshipRecord)
                .where(
                    SourceRelationshipRecord.task_id == task_id,
                    SourceRelationshipRecord.lifecycle == "active",
                    or_(
                        SourceRelationshipRecord.source_low_id == source_id,
                        SourceRelationshipRecord.source_high_id == source_id,
                    ),
                )
                .order_by(SourceRelationshipRecord.relationship_id)
                .limit(self.LIMITS.max_examined_relationships + 1)
            ).all()
            for record in records:
                if record.relationship_id not in examined:
                    if len(examined) >= self.LIMITS.max_examined_relationships:
                        overflow = "edge_limit"
                        break
                    examined[record.relationship_id] = record
                neighbor = (
                    record.source_high_id
                    if record.source_low_id == source_id
                    else record.source_low_id
                )
                if neighbor in visited:
                    continue
                if depth >= self.LIMITS.max_hops:
                    frontier.add(neighbor)
                    overflow = "depth_limit"
                    continue
                if len(visited) >= self.LIMITS.max_visited_sources:
                    frontier.add(neighbor)
                    overflow = "node_limit"
                    continue
                visited.add(neighbor)
                depths[neighbor] = depth + 1
                queue.append(neighbor)
        if overflow is None and queue:
            overflow = "node_limit"
        return SourceDependenceProjection(
            task_id=task_id,
            complete=overflow is None,
            truncated=overflow is not None,
            limits=self.LIMITS,
            visited_source_ids=sorted(visited, key=lambda item: item.int),
            examined_relationships=[
                self._state_from_record(record)
                for record in sorted(examined.values(), key=lambda item: item.relationship_id.int)
            ],
            frontier_source_ids=sorted(frontier, key=lambda item: item.int),
            overflow_reason=overflow,
            unknown_dependence=True,
        )

    def _commit_change(
        self,
        task_id: UUID,
        current: SourceRelationshipRecord,
        *,
        lifecycle: str,
        direction: str,
        operation: Literal["SET", "RETRACT", "REVERSE"],
        operation_id: UUID,
        reason: str,
        authority: PersistedSecurityState,
        reverses_change_id: UUID | None = None,
        previous_state_override: SourceRelationship | None = None,
    ) -> SourceRelationship:
        previous = previous_state_override or self._state_from_record(current)
        change_id = uuid4()
        now = datetime.now(UTC)
        state = self._state(
            relationship_id=current.relationship_id,
            task_id=task_id,
            low_id=current.source_low_id,
            high_id=current.source_high_id,
            kind=current.kind,
            direction=direction,
            lifecycle=lifecycle,
            revision=current.revision + 1,
            latest_change_id=change_id,
            updated_at=now,
        )
        current.direction = direction
        current.lifecycle = lifecycle
        current.revision = state.revision
        current.latest_change_id = change_id
        current.updated_at = now
        self.session.add(
            self._change_record(
                change_id=change_id,
                operation_id=operation_id,
                state=state,
                previous_state=previous,
                previous_revision=previous.revision,
                operation=operation,
                reason=reason,
                authority=authority,
                reverses_change_id=reverses_change_id,
            )
        )
        self._stage_audit(task_id, operation_id, state)
        self.session.commit()
        return state

    def _normalize_create(
        self, task_id: UUID, request: SourceRelationshipCreate
    ) -> tuple[UUID, UUID, UUID, UUID, str]:
        if request.kind is SourceDependenceKind.DERIVED_FROM:
            if (
                request.derived_source_id is None
                or request.upstream_source_id is None
                or request.source_a_id is not None
                or request.source_b_id is not None
            ):
                raise SourceDependenceConflict(
                    "Derived relationships require derived/upstream endpoints"
                )
            derived_id, upstream_id = request.derived_source_id, request.upstream_source_id
        else:
            if (
                request.source_a_id is None
                or request.source_b_id is None
                or request.derived_source_id is not None
                or request.upstream_source_id is not None
            ):
                raise SourceDependenceConflict(
                    "Common-origin relationships require two symmetric endpoints"
                )
            derived_id = upstream_id = request.source_a_id
            upstream_id = request.source_b_id
        if derived_id == upstream_id:
            raise SourceDependenceConflict("A source relationship cannot reference itself")
        low_id, high_id = sorted((derived_id, upstream_id), key=lambda item: item.int)
        if request.kind is SourceDependenceKind.COMMON_ORIGIN:
            return derived_id, upstream_id, low_id, high_id, "none"
        direction = "low_to_high" if derived_id == low_id else "high_to_low"
        return derived_id, upstream_id, low_id, high_id, direction

    def _validate_sources(self, task_id: UUID, *source_ids: UUID) -> None:
        if not source_ids:
            return
        found = set(
            self.session.scalars(
                select(ResearchSourceRecord.id).where(
                    ResearchSourceRecord.task_id == task_id,
                    ResearchSourceRecord.id.in_(set(source_ids)),
                )
            )
        )
        if found != set(source_ids):
            raise SourceDependenceConflict("Every relationship endpoint must belong to the task")

    def _validate_no_cycle(
        self,
        task_id: UUID,
        derived_id: UUID,
        upstream_id: UUID,
        excluded_relationship_id: UUID | None = None,
    ) -> None:
        queue: deque[tuple[UUID, int]] = deque([(upstream_id, 0)])
        visited = {upstream_id}
        examined = 0
        while queue:
            source_id, depth = queue.popleft()
            records = self.session.scalars(
                select(SourceRelationshipRecord)
                .where(
                    SourceRelationshipRecord.task_id == task_id,
                    SourceRelationshipRecord.lifecycle == "active",
                    SourceRelationshipRecord.kind == SourceDependenceKind.DERIVED_FROM.value,
                    or_(
                        SourceRelationshipRecord.source_low_id == source_id,
                        SourceRelationshipRecord.source_high_id == source_id,
                    ),
                )
                .order_by(SourceRelationshipRecord.relationship_id)
            )
            for record in records:
                if record.relationship_id == excluded_relationship_id:
                    continue
                examined += 1
                if examined > self.LIMITS.max_examined_relationships:
                    raise SourceDependenceConflict("Graph validation limit prevents cycle proof")
                edge_derived, edge_upstream = self._directional_endpoints(record, record.direction)
                if edge_derived != source_id:
                    continue
                if edge_upstream == derived_id:
                    raise SourceDependenceConflict("Source relationship would create a cycle")
                if edge_upstream in visited:
                    continue
                if depth >= self.LIMITS.max_hops:
                    raise SourceDependenceConflict("Graph validation limit prevents cycle proof")
                visited.add(edge_upstream)
                queue.append((edge_upstream, depth + 1))

    def _lock_task(self, task_id: UUID) -> None:
        if self.session.scalar(
            select(ResearchTaskRecord.id)
            .where(ResearchTaskRecord.id == task_id)
            .with_for_update()
        ) is None:
            raise SourceDependenceNotFound("Research task was not found")

    def _relationship_for_update(
        self, task_id: UUID, relationship_id: UUID
    ) -> SourceRelationshipRecord:
        record = self.session.scalar(
            select(SourceRelationshipRecord)
            .where(
                SourceRelationshipRecord.task_id == task_id,
                SourceRelationshipRecord.relationship_id == relationship_id,
            )
            .with_for_update()
        )
        if record is None:
            raise SourceDependenceNotFound("Source relationship was not found")
        return record

    def _operation_change(self, operation_id: UUID) -> SourceRelationshipChangeRecord | None:
        return self.session.scalar(
            select(SourceRelationshipChangeRecord).where(
                SourceRelationshipChangeRecord.operation_id == operation_id
            )
        )

    def _retry_or_conflict(
        self,
        change: SourceRelationshipChangeRecord,
        *,
        task_id: UUID,
        relationship_id: UUID | None,
        kind: str,
        direction: str,
        lifecycle: str,
        source_low_id: UUID | None = None,
        source_high_id: UUID | None = None,
    ) -> SourceRelationship:
        state = change.resulting_state
        if (
            change.task_id != task_id
            or (relationship_id is not None and change.relationship_id != relationship_id)
            or state.get("kind") != kind
            or state.get("direction") != direction
            or state.get("lifecycle") != lifecycle
            or (source_low_id is not None and state.get("source_low_id") != str(source_low_id))
            or (source_high_id is not None and state.get("source_high_id") != str(source_high_id))
        ):
            raise SourceDependenceConflict("Operation identity was reused with different content")
        current = self.session.get(SourceRelationshipRecord, change.relationship_id)
        if current is None:
            raise SourceDependenceConflict("Accepted relationship projection is unavailable")
        return self._state_from_record(current)

    @staticmethod
    def _directional_endpoints(
        record: SourceRelationshipRecord, direction: str
    ) -> tuple[UUID, UUID]:
        if direction == "low_to_high":
            return record.source_low_id, record.source_high_id
        if direction == "high_to_low":
            return record.source_high_id, record.source_low_id
        raise SourceDependenceConflict("Common-origin relationships have no direction")

    @staticmethod
    def _validate_direction(kind: str, direction: str) -> None:
        if kind == SourceDependenceKind.COMMON_ORIGIN.value and direction != "none":
            raise SourceDependenceConflict("Common-origin relationships must be symmetric")
        if kind == SourceDependenceKind.DERIVED_FROM.value and direction not in {
            "low_to_high",
            "high_to_low",
        }:
            raise SourceDependenceConflict("Derived relationships require a direction")

    @staticmethod
    def _state(
        *,
        relationship_id: UUID,
        task_id: UUID,
        low_id: UUID,
        high_id: UUID,
        kind: str,
        direction: str,
        lifecycle: str,
        revision: int,
        latest_change_id: UUID,
        updated_at: datetime,
    ) -> SourceRelationship:
        return SourceRelationship(
            relationship_id=relationship_id,
            task_id=task_id,
            source_low_id=low_id,
            source_high_id=high_id,
            kind=SourceDependenceKind(kind),
            direction=direction,  # type: ignore[arg-type]
            lifecycle=SourceRelationshipLifecycle(lifecycle),
            revision=revision,
            latest_change_id=latest_change_id,
            updated_at=updated_at,
        )

    @staticmethod
    def _record_from_state(state: SourceRelationship) -> SourceRelationshipRecord:
        return SourceRelationshipRecord(
            relationship_id=state.relationship_id,
            task_id=state.task_id,
            source_low_id=state.source_low_id,
            source_high_id=state.source_high_id,
            kind=state.kind.value,
            direction=state.direction,
            lifecycle=state.lifecycle.value,
            revision=state.revision,
            latest_change_id=state.latest_change_id,
            updated_at=state.updated_at,
        )

    def _change_record(
        self,
        *,
        change_id: UUID,
        operation_id: UUID,
        state: SourceRelationship,
        previous_state: SourceRelationship | None,
        previous_revision: int,
        operation: str,
        reason: str,
        authority: PersistedSecurityState,
        reverses_change_id: UUID | None = None,
    ) -> SourceRelationshipChangeRecord:
        return SourceRelationshipChangeRecord(
            change_id=change_id,
            operation_id=operation_id,
            relationship_id=state.relationship_id,
            task_id=state.task_id,
            previous_revision=previous_revision,
            revision=state.revision,
            operation=cast(Literal["CREATE", "SET", "RETRACT", "REVERSE"], operation),
            previous_state=previous_state.model_dump(mode="json") if previous_state else None,
            resulting_state=state.model_dump(mode="json"),
            actor_type=self.actor.actor_type,
            actor_id=self.actor.actor_id,
            reason=reason,
            authority_epoch_id=authority.authority_epoch_id.value,
            security_state_version=authority.version,
            reverses_change_id=reverses_change_id,
            created_at=state.updated_at,
        )

    def _stage_audit(self, task_id: UUID, operation_id: UUID, state: SourceRelationship) -> None:
        AuditService(self.session).stage(
            task_id,
            EventType.SOURCE_DEPENDENCE_CHANGED,
            EventPayload(
                operation_id=operation_id,
                relationship_id=state.relationship_id,
                dependence_kind=state.kind.value,
                dependence_direction=state.direction,
                relationship_lifecycle=state.lifecycle.value,
                relationship_revision=state.revision,
                actor="local_operator",
                provenance=[state.source_low_id, state.source_high_id],
                result="committed",
            ),
        )

    @staticmethod
    def _state_from_record(record: SourceRelationshipRecord) -> SourceRelationship:
        return SourceRelationship.model_validate(record, from_attributes=True)

    @staticmethod
    def _change_from_record(record: SourceRelationshipChangeRecord) -> SourceRelationshipChange:
        return SourceRelationshipChange(
            change_id=record.change_id,
            operation_id=record.operation_id,
            relationship_id=record.relationship_id,
            task_id=record.task_id,
            previous_revision=record.previous_revision,
            revision=record.revision,
            operation=cast(Literal["CREATE", "SET", "RETRACT", "REVERSE"], record.operation),
            previous_state=(
                SourceRelationship.model_validate(record.previous_state)
                if record.previous_state is not None
                else None
            ),
            resulting_state=SourceRelationship.model_validate(record.resulting_state),
            actor_type=cast(Literal["local_operator"], record.actor_type),
            actor_id=record.actor_id,
            reason=record.reason,
            authority_epoch_id=record.authority_epoch_id,
            security_state_version=record.security_state_version,
            reverses_change_id=record.reverses_change_id,
            created_at=record.created_at,
        )
