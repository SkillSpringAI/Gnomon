"""SQLAlchemy repositories for durable research task state."""

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from research_agent.application.audit_service import AuditService
from research_agent.application.research_service import ResearchTaskNotFound
from research_agent.domain.events import EventPayload, EventType
from research_agent.domain.research import (
    CyclePlanningBasis,
    CycleStatus,
    InvestigationPlan,
    ResearchBrief,
    ResearchCycle,
    ResearchMethod,
    ResearchTask,
    TaskStatus,
)
from research_agent.domain.snapshot import InvestigationSnapshot
from research_agent.persistence.models import ResearchCycleRecord, ResearchTaskRecord


class SqlAlchemyResearchTaskRepository:
    """Persist and retrieve research tasks through SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, task: ResearchTask) -> ResearchTask:
        try:
            self._stage(task)
            self.session.commit()
            return task
        except Exception:
            self.session.rollback()
            raise

    def _stage(self, task: ResearchTask) -> None:
        record = self.session.get(ResearchTaskRecord, task.id)
        if record is None:
            record = ResearchTaskRecord(
                id=task.id,
                title=task.brief.title,
                objective=task.brief.objective,
                status=task.status.value,
                brief=task.brief.model_dump(mode="json"),
                plan=task.plan.model_dump(mode="json"),
                created_at=task.created_at,
                updated_at=task.updated_at,
            )
            self.session.add(record)
            # Establish the task row before inserting its foreign-keyed audit event.
            self.session.flush()
            AuditService(self.session).stage(
                task.id,
                EventType.TASK_CREATED,
                EventPayload(
                    operation_id=uuid4(),
                    actor="local_operator",
                    result="committed",
                ),
            )
        else:
            record.status = task.status.value
            record.brief = task.brief.model_dump(mode="json")
            record.plan = task.plan.model_dump(mode="json")
            record.updated_at = task.updated_at

        existing = {cycle.cycle_number: cycle for cycle in record.cycles}
        numbers = [cycle.number for cycle in task.cycles]
        if len(set(numbers)) != len(numbers) or not set(existing).issubset(numbers):
            raise ValueError("Cycle history must retain unique existing cycle numbers")
        for cycle in task.cycles:
            cycle_record = existing.get(cycle.number)
            if cycle_record is None:
                cycle_record = ResearchCycleRecord(
                    id=uuid4(),
                    task_id=task.id,
                    cycle_number=cycle.number,
                    planning_basis=[
                        basis.model_dump(mode="json") for basis in cycle.planning_basis
                    ],
                    objectives=cycle.objectives,
                    methods=[method.value for method in cycle.methods],
                    status=cycle.status.value,
                    created_at=cycle.created_at,
                    started_at=cycle.started_at,
                    completed_at=cycle.completed_at,
                    result_summary=cycle.result_summary,
                    evidence_ids=[str(item) for item in cycle.evidence_ids],
                    claim_ids=[str(item) for item in cycle.claim_ids],
                    unresolved_objectives=cycle.unresolved_objectives,
                    attempted_objectives=cycle.attempted_objectives,
                )
                record.cycles.append(cycle_record)
            else:
                cycle_record.objectives = cycle.objectives
                cycle_record.methods = [method.value for method in cycle.methods]
                cycle_record.status = cycle.status.value
                cycle_record.planning_basis = [
                    basis.model_dump(mode="json") for basis in cycle.planning_basis
                ]
                cycle_record.started_at = cycle.started_at
                cycle_record.completed_at = cycle.completed_at
                cycle_record.result_summary = cycle.result_summary
                cycle_record.evidence_ids = [str(item) for item in cycle.evidence_ids]
                cycle_record.claim_ids = [str(item) for item in cycle.claim_ids]
                cycle_record.unresolved_objectives = cycle.unresolved_objectives
                cycle_record.attempted_objectives = cycle.attempted_objectives

    @contextmanager
    def edit(self, task_id: UUID) -> Iterator[ResearchTask]:
        try:
            task = self.get(task_id, for_update=True)
            before = task.model_copy(deep=True)
            yield task
            if task != before:
                self._stage(task)
                operation_id = uuid4()
                audit = AuditService(self.session)
                if task.status != before.status:
                    audit.stage(
                        task_id,
                        EventType.TASK_STATUS_CHANGED,
                        EventPayload(
                            operation_id=operation_id,
                            from_status=before.status,
                            to_status=task.status,
                            actor="local_operator",
                            result="committed",
                        ),
                    )
                previous_numbers = {cycle.number for cycle in before.cycles}
                for cycle in task.cycles:
                    if cycle.number not in previous_numbers:
                        audit.stage(
                            task_id,
                            EventType.CYCLE_PLANNED,
                            EventPayload(
                                operation_id=operation_id,
                                cycle_number=cycle.number,
                                actor="local_operator",
                                result="committed",
                            ),
                        )
                before_cycles = {cycle.number: cycle for cycle in before.cycles}
                for cycle in task.cycles:
                    previous = before_cycles.get(cycle.number)
                    if previous is None:
                        continue
                    if cycle.status != previous.status:
                        audit.stage(
                            task_id,
                            EventType.CYCLE_STARTED
                            if cycle.status.value == "active"
                            else EventType.CYCLE_OUTCOME_RECORDED,
                            EventPayload(
                                operation_id=operation_id,
                                cycle_number=cycle.number,
                                from_status=previous.status,
                                to_status=cycle.status,
                                claim_count=len(cycle.claim_ids),
                                unresolved_count=len(cycle.unresolved_objectives),
                                actor="local_operator",
                                result="committed",
                            ),
                        )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def get(self, task_id: UUID, *, for_update: bool = False) -> ResearchTask:
        statement = (
            select(ResearchTaskRecord)
            .options(selectinload(ResearchTaskRecord.cycles))
            .where(ResearchTaskRecord.id == task_id)
        )
        if for_update:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        record = self.session.scalar(statement)
        if record is None:
            raise ResearchTaskNotFound

        payload = record.brief | {
            "title": record.title,
            "objective": record.objective,
        }
        return ResearchTask(
            id=record.id,
            brief=ResearchBrief.model_validate(payload),
            plan=InvestigationPlan.model_validate(record.plan),
            status=TaskStatus(record.status),
            cycles=[
                ResearchCycle(
                    number=cycle.cycle_number,
                    planning_basis=[
                        CyclePlanningBasis.model_validate(basis) for basis in cycle.planning_basis
                    ],
                    objectives=cycle.objectives,
                    methods=[ResearchMethod(method) for method in cycle.methods],
                    status=CycleStatus(cycle.status),
                    created_at=cycle.created_at,
                    started_at=cycle.started_at,
                    completed_at=cycle.completed_at,
                    result_summary=cycle.result_summary,
                    evidence_ids=[UUID(item) for item in cycle.evidence_ids],
                    claim_ids=[UUID(item) for item in cycle.claim_ids],
                    unresolved_objectives=cycle.unresolved_objectives,
                    attempted_objectives=cycle.attempted_objectives,
                )
                for cycle in record.cycles
            ],
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def planning_snapshot(self, task_id: UUID) -> InvestigationSnapshot:
        # Snapshot assembly also uses this repository for the task read.
        from research_agent.application.snapshot_service import SnapshotService

        return SnapshotService(self.session).get(task_id)
