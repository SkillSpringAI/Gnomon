"""Application service for creating and continuing investigations."""

from collections.abc import Iterator
from contextlib import contextmanager
from threading import RLock
from uuid import UUID

from research_agent.application.cycle_planner import plan_cycle_objectives
from research_agent.domain.research import (
    CycleOutcomeCreate,
    CycleStatus,
    InvestigationPlan,
    ResearchBrief,
    ResearchCycle,
    ResearchTask,
    TaskStatus,
    TaskStatusChange,
    utc_now,
)
from research_agent.domain.snapshot import HypothesisSnapshot, InvestigationSnapshot
from research_agent.ports.research_repository import ResearchTaskRepository


class ResearchTaskNotFound(Exception):
    """Raised when an investigation identifier is unknown."""


class TaskStateConflict(Exception):
    """A stale or disallowed lifecycle operation."""


class CycleNotFound(Exception):
    """Raised when a cycle number is unknown."""


class InMemoryResearchTaskRepository:
    """Development task storage; PostgreSQL supplies durable audit and concurrency."""

    def __init__(self) -> None:
        self._tasks: dict[UUID, ResearchTask] = {}
        self._lock = RLock()

    def save(self, task: ResearchTask) -> ResearchTask:
        self._tasks[task.id] = task.model_copy(deep=True)
        return task

    def get(self, task_id: UUID) -> ResearchTask:
        try:
            return self._tasks[task_id].model_copy(deep=True)
        except KeyError as exc:
            raise ResearchTaskNotFound from exc

    def planning_snapshot(self, task_id: UUID) -> InvestigationSnapshot:
        task = self.get(task_id)
        return InvestigationSnapshot(
            task=task,
            hypotheses=[
                HypothesisSnapshot(
                    hypothesis=hypothesis, assessment_state="not_assessed", assessment=None
                )
                for hypothesis in task.brief.hypotheses
            ],
            claims=[],
            sources=[],
            open_questions=task.plan.open_questions,
        )

    @contextmanager
    def edit(self, task_id: UUID) -> Iterator[ResearchTask]:
        with self._lock:
            task = self.get(task_id)
            yield task
            self.save(task)


class ResearchService:
    """Coordinate investigation creation and bounded next-cycle planning."""

    def __init__(self, repository: ResearchTaskRepository) -> None:
        self.repository = repository

    def create_task(self, brief: ResearchBrief) -> ResearchTask:
        methods = brief.methods or []
        objectives = [
            brief.questions[0].question
            if brief.questions
            else "Define the evidence base and competing explanations for the investigation."
        ]
        plan = InvestigationPlan(
            summary=f"Investigate: {brief.objective}",
            first_cycle_objectives=objectives,
            proposed_methods=methods,
            open_questions=[question.question for question in brief.questions],
        )
        task = ResearchTask(
            brief=brief,
            plan=plan,
            status=TaskStatus.ACTIVE,
            cycles=[
                ResearchCycle(
                    number=1,
                    objectives=objectives,
                    methods=methods,
                )
            ],
        )
        return self.repository.save(task)

    def get_task(self, task_id: UUID) -> ResearchTask:
        return self.repository.get(task_id)

    def plan_next_cycle(self, task_id: UUID) -> ResearchTask:
        with self.repository.edit(task_id) as task:
            if task.status != TaskStatus.ACTIVE:
                raise TaskStateConflict("New cycles require an active investigation")
            if any(cycle.status == CycleStatus.ACTIVE for cycle in task.cycles):
                raise TaskStateConflict("Complete the active cycle before planning another")
            next_number = max((cycle.number for cycle in task.cycles), default=0) + 1
            objectives, basis = plan_cycle_objectives(self.repository.planning_snapshot(task_id))
            task.cycles.append(
                ResearchCycle(
                    number=next_number,
                    objectives=objectives,
                    planning_basis=basis,
                    methods=task.brief.methods,
                )
            )
            task.updated_at = utc_now()
        return task

    def start_cycle(self, task_id: UUID, cycle_number: int) -> ResearchTask:
        with self.repository.edit(task_id) as task:
            if task.status != TaskStatus.ACTIVE:
                raise TaskStateConflict("Cycles require an active investigation")
            cycle = self._cycle(task, cycle_number)
            if cycle.status == CycleStatus.ACTIVE:
                return task
            if cycle.status != CycleStatus.PLANNED:
                raise TaskStateConflict("Only a planned cycle can be started")
            cycle.status = CycleStatus.ACTIVE
            cycle.started_at = utc_now()
            task.updated_at = utc_now()
        return task

    def record_cycle_outcome(
        self, task_id: UUID, cycle_number: int, outcome: CycleOutcomeCreate
    ) -> ResearchTask:
        with self.repository.edit(task_id) as task:
            cycle = self._cycle(task, cycle_number)
            if cycle.status != CycleStatus.ACTIVE:
                raise TaskStateConflict("Only an active cycle can record an outcome")
            snapshot = self.repository.planning_snapshot(task_id)
            source_ids = {source.id for source in snapshot.sources}
            claim_ids = {claim.id for claim in snapshot.claims}
            if not set(outcome.evidence_ids).issubset(source_ids):
                raise TaskStateConflict("Outcome references evidence outside this investigation")
            if not set(outcome.claim_ids).issubset(claim_ids):
                raise TaskStateConflict("Outcome references claims outside this investigation")
            cycle.status = CycleStatus(outcome.status)
            cycle.result_summary = outcome.result_summary
            cycle.evidence_ids = list(outcome.evidence_ids)
            cycle.claim_ids = list(outcome.claim_ids)
            cycle.unresolved_objectives = list(outcome.unresolved_objectives)
            cycle.completed_at = utc_now()
            task.updated_at = utc_now()
        return task

    @staticmethod
    def _cycle(task: ResearchTask, cycle_number: int) -> ResearchCycle:
        for cycle in task.cycles:
            if cycle.number == cycle_number:
                return cycle
        raise CycleNotFound

    def change_status(self, task_id: UUID, change: TaskStatusChange) -> ResearchTask:
        allowed = {
            TaskStatus.PLANNED: {TaskStatus.ACTIVE, TaskStatus.BLOCKED, TaskStatus.ABANDONED},
            TaskStatus.ACTIVE: {
                TaskStatus.PAUSED,
                TaskStatus.BLOCKED,
                TaskStatus.CONCLUDED,
                TaskStatus.ABANDONED,
            },
            TaskStatus.PAUSED: {
                TaskStatus.ACTIVE,
                TaskStatus.BLOCKED,
                TaskStatus.CONCLUDED,
                TaskStatus.ABANDONED,
            },
            TaskStatus.BLOCKED: {
                TaskStatus.ACTIVE,
                TaskStatus.PAUSED,
                TaskStatus.CONCLUDED,
                TaskStatus.ABANDONED,
            },
            TaskStatus.CONCLUDED: set(),
            TaskStatus.ABANDONED: set(),
        }
        with self.repository.edit(task_id) as task:
            if task.status == change.status:
                return task
            if task.status != change.expected_status:
                raise TaskStateConflict("Investigation status changed; reload before retrying")
            if change.status not in allowed[task.status]:
                raise TaskStateConflict("This investigation status transition is not permitted")
            task.status = change.status
            task.updated_at = utc_now()
        return task
