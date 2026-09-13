"""Application service for creating and continuing investigations."""

from collections.abc import Iterator
from contextlib import contextmanager
from threading import RLock
from uuid import UUID

from research_agent.application.cycle_planner import (
    objective_basis,
    plan_cycle_objectives,
    reference_fingerprint,
    review_evidence_fingerprint,
)
from research_agent.domain.research import (
    CycleObjectiveResult,
    CycleOutcomeCreate,
    CycleRecoveryCreate,
    CycleStatus,
    InvestigationPlan,
    ObjectiveReview,
    ObjectiveReviewCreate,
    ResearchBrief,
    ResearchCycle,
    ResearchMethod,
    ResearchTask,
    TaskStatus,
    TaskStatusChange,
    recovery_fingerprint,
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


class InvalidCycleSelection(ValueError):
    """Requested execution does not match the saved cycle plan."""


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
            if not objectives:
                raise TaskStateConflict("No pending objectives for the current evidence")
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

    def review_objective(
        self,
        task_id: UUID,
        cycle_number: int,
        objective_index: int,
        request: ObjectiveReviewCreate,
    ) -> ResearchTask:
        with self.repository.edit(task_id) as task:
            cycle = self._cycle(task, cycle_number)
            if (
                task.status not in {TaskStatus.ACTIVE, TaskStatus.PAUSED}
                or cycle_number != max(item.number for item in task.cycles)
                or cycle.status
                not in {CycleStatus.COMPLETED, CycleStatus.BLOCKED, CycleStatus.FAILED}
            ):
                raise TaskStateConflict("Review the latest finished cycle before planning another")
            if objective_index < 0 or objective_index >= len(cycle.objectives):
                raise InvalidCycleSelection("Objective does not belong to this cycle")
            reviews = [
                item for item in cycle.objective_reviews if item.objective_index == objective_index
            ]
            if request.expected_revision != len(reviews) or len(cycle.objective_reviews) >= 100:
                raise TaskStateConflict(
                    "Review history changed or reached its limit; refresh the report"
                )
            snapshot = self.repository.planning_snapshot(task_id)
            if request.expected_evidence_fingerprint != review_evidence_fingerprint(snapshot):
                raise TaskStateConflict("Evidence changed; refresh and review the current evidence")
            if not set(request.source_ids).issubset({item.id for item in snapshot.sources}):
                raise InvalidCycleSelection("Review sources must belong to this investigation")
            if not set(request.claim_ids).issubset({item.id for item in snapshot.claims}):
                raise InvalidCycleSelection("Review claims must be active in this investigation")
            if request.decision == "completed" and not (request.source_ids or request.claim_ids):
                raise InvalidCycleSelection("Completing a review requires evidence references")
            review = ObjectiveReview(
                objective_index=objective_index,
                objective=cycle.objectives[objective_index],
                revision=len(reviews) + 1,
                decision=request.decision,
                rationale=request.rationale,
                source_ids=list(dict.fromkeys(request.source_ids)),
                claim_ids=list(dict.fromkeys(request.claim_ids)),
                basis=objective_basis(cycle, objective_index, snapshot),
                reference_fingerprint="",
            )
            review.reference_fingerprint = reference_fingerprint(review, snapshot)
            cycle.objective_reviews.append(review)
            task.updated_at = utc_now()
        return task

    def start_cycle(
        self,
        task_id: UUID,
        cycle_number: int,
        *,
        exclusive: bool = False,
        objective_indices: list[int] | None = None,
        required_method: ResearchMethod | None = None,
        track_progress: bool = False,
    ) -> ResearchTask:
        with self.repository.edit(task_id) as task:
            if task.status != TaskStatus.ACTIVE:
                raise TaskStateConflict("Cycles require an active investigation")
            cycle = self._cycle(task, cycle_number)
            if objective_indices is not None and (
                not objective_indices
                or any(
                    type(index) is not int or index < 0 or index >= len(cycle.objectives)
                    for index in objective_indices
                )
            ):
                raise InvalidCycleSelection("Objective selection does not match the cycle plan")
            if required_method is not None:
                for methods in (task.brief.methods, cycle.methods):
                    if methods and required_method not in methods:
                        raise InvalidCycleSelection("Research method is not allowed by this plan")
            if any(
                item.status == CycleStatus.ACTIVE and (exclusive or item.number != cycle_number)
                for item in task.cycles
            ):
                raise TaskStateConflict("An investigation cycle is already active")
            if cycle.status == CycleStatus.ACTIVE:
                return task
            if cycle.status != CycleStatus.PLANNED:
                raise TaskStateConflict("Only a planned cycle can be started")
            cycle.status = CycleStatus.ACTIVE
            cycle.started_at = utc_now()
            cycle.progress_tracked = track_progress
            task.updated_at = utc_now()
        return task

    def recover_cycle(
        self, task_id: UUID, cycle_number: int, request: CycleRecoveryCreate
    ) -> ResearchTask:
        with self.repository.edit(task_id) as task:
            cycle = self._cycle(task, cycle_number)
            if cycle.status != CycleStatus.ACTIVE:
                raise TaskStateConflict("Only an active cycle can be recovered")
            if request.expected_fingerprint != recovery_fingerprint(task.status, cycle):
                raise TaskStateConflict("Cycle progress changed; refresh before recovery")
            cycle.status = CycleStatus.FAILED
            cycle.result_summary = "Operator recovery: " + request.reason
            cycle.recovery_reason = request.reason
            cycle.unresolved_objectives = list(cycle.objectives)
            cycle.completed_at = utc_now()
            if task.status == TaskStatus.ACTIVE:
                task.status = TaskStatus.PAUSED
            task.updated_at = utc_now()
        return task

    def record_cycle_outcome(
        self,
        task_id: UUID,
        cycle_number: int,
        outcome: CycleOutcomeCreate,
        *,
        require_active_task: bool = False,
    ) -> ResearchTask:
        with self.repository.edit(task_id) as task:
            if require_active_task and task.status != TaskStatus.ACTIVE:
                raise TaskStateConflict("Investigation stopped during cycle execution")
            cycle = self._cycle(task, cycle_number)
            if cycle.status != CycleStatus.ACTIVE:
                raise TaskStateConflict("Only an active cycle can record an outcome")
            # A manual or late runner outcome must retain previously committed progress.
            results = {
                item.objective_index: item.model_copy(deep=True) for item in cycle.objective_results
            }
            for item in outcome.objective_results:
                saved = results.setdefault(
                    item.objective_index, CycleObjectiveResult(objective_index=item.objective_index)
                )
                saved.source_ids = list(dict.fromkeys(saved.source_ids + item.source_ids))
                saved.claim_ids = list(dict.fromkeys(saved.claim_ids + item.claim_ids))
            # Keep duplicate-index validation on the submitted payload before merging.
            if len({item.objective_index for item in outcome.objective_results}) != len(
                outcome.objective_results
            ):
                raise TaskStateConflict("Objective results require unique saved objective indexes")
            outcome = outcome.model_copy(
                update={
                    "evidence_ids": list(dict.fromkeys(cycle.evidence_ids + outcome.evidence_ids)),
                    "claim_ids": list(dict.fromkeys(cycle.claim_ids + outcome.claim_ids)),
                    "attempted_objectives": list(
                        dict.fromkeys(cycle.attempted_objectives + outcome.attempted_objectives)
                    ),
                    "objective_results": list(results.values()),
                }
            )
            if (
                len(outcome.evidence_ids) > 100
                or len(outcome.claim_ids) > 100
                or len(outcome.attempted_objectives) > 3
                or len(outcome.objective_results) > 3
            ):
                raise TaskStateConflict("Outcome exceeds bounded cycle progress")
            snapshot = self.repository.planning_snapshot(task_id)
            source_ids = {source.id for source in snapshot.sources}
            claim_ids = {claim.id for claim in snapshot.claims}
            if not set(outcome.evidence_ids).issubset(source_ids):
                raise TaskStateConflict("Outcome references evidence outside this investigation")
            if not set(outcome.claim_ids).issubset(claim_ids):
                raise TaskStateConflict("Outcome references claims outside this investigation")
            objectives = set(cycle.objectives)
            if not set(outcome.attempted_objectives).issubset(objectives):
                raise TaskStateConflict("Outcome references attempted work outside this cycle")
            if not set(outcome.unresolved_objectives).issubset(objectives):
                raise TaskStateConflict("Outcome references unresolved work outside this cycle")
            seen_indices: set[int] = set()
            claims_by_id = {claim.id: claim for claim in snapshot.claims}
            for result in outcome.objective_results:
                index = result.objective_index
                if index >= len(cycle.objectives) or index in seen_indices:
                    raise TaskStateConflict(
                        "Objective results require unique saved objective indexes"
                    )
                seen_indices.add(index)
                if cycle.objectives[index] not in outcome.attempted_objectives:
                    raise TaskStateConflict("Objective result must describe attempted work")
                if not set(result.source_ids).issubset(outcome.evidence_ids):
                    raise TaskStateConflict("Objective sources must belong to the cycle outcome")
                if not set(result.claim_ids).issubset(outcome.claim_ids):
                    raise TaskStateConflict("Objective claims must belong to the cycle outcome")
                for claim_id in result.claim_ids:
                    if not any(
                        link.source_id in result.source_ids
                        for link in claims_by_id[claim_id].source_links
                    ):
                        raise TaskStateConflict("Objective claims must cite an associated source")
            cycle.objective_results = [
                item.model_copy(deep=True) for item in outcome.objective_results
            ]
            cycle.status = CycleStatus(outcome.status)
            cycle.result_summary = outcome.result_summary
            cycle.evidence_ids = list(outcome.evidence_ids)
            cycle.claim_ids = list(outcome.claim_ids)
            cycle.unresolved_objectives = list(outcome.unresolved_objectives)
            cycle.attempted_objectives = list(outcome.attempted_objectives)
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
