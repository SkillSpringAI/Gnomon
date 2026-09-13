"""Run one bounded local agent-research cycle end to end."""

from uuid import UUID

from sqlalchemy.orm import Session

from research_agent.adapters.agents.fake import FakeAgentNetwork, FakeScenario
from research_agent.application.agent_evidence_service import AgentEvidenceService
from research_agent.application.claim_extraction_service import ClaimExtractionService
from research_agent.application.cycle_progress import CycleProgress
from research_agent.application.research_service import ResearchService, TaskStateConflict
from research_agent.domain.agents import AgentQuestion
from research_agent.domain.research import (
    CycleObjectiveResult,
    CycleOutcomeCreate,
    CycleStatus,
    ResearchTask,
    TaskStatus,
)
from research_agent.persistence.repositories import SqlAlchemyResearchTaskRepository
from research_agent.ports.agent_network import AgentNetworkError
from research_agent.security.agent_policy import AgentRunPolicy
from research_agent.security.boundaries import BoundaryViolation


class AgentCycleRunner:
    """Local prototype orchestration; no outbound or autonomous side effects."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def run(
        self,
        task_id: UUID,
        cycle_number: int,
        *,
        scenario: FakeScenario = FakeScenario.HONEST,
        max_agents: int = 2,
        objective_indices: list[int] | None = None,
    ) -> ResearchTask:
        network = FakeAgentNetwork(scenario)
        policy = AgentRunPolicy(max_agents=max_agents)
        repository = SqlAlchemyResearchTaskRepository(self.session)
        research = ResearchService(repository)
        planned_task = repository.get(task_id)
        planned_cycle = next(
            (item for item in planned_task.cycles if item.number == cycle_number), None
        )
        if planned_cycle is None:
            raise ValueError("Cycle does not exist")
        selected_indices = [0] if objective_indices is None else objective_indices
        if (
            not selected_indices
            or len(selected_indices) > 3
            or len(set(selected_indices)) != len(selected_indices)
            or any(
                type(index) is not int or index < 0 or index >= len(planned_cycle.objectives)
                for index in selected_indices
            )
        ):
            raise ValueError("Objective selection must contain unique cycle objective indexes")
        selected_objectives = [planned_cycle.objectives[index] for index in selected_indices]
        task = research.start_cycle(task_id, cycle_number, exclusive=True, track_progress=True)
        cycle = next(cycle for cycle in task.cycles if cycle.number == cycle_number)
        evidence_ids: list[UUID] = []
        claim_ids: list[UUID] = []
        results: dict[int, CycleObjectiveResult] = {}
        progress = CycleProgress(self.session, task_id, cycle_number)

        def mark_attempted() -> None:
            progress.attempt(selected_indices)
            for index in selected_indices:
                results.setdefault(index, CycleObjectiveResult(objective_index=index))

        def guard() -> None:
            current = repository.get(task_id, for_update=True)
            current_cycle = next(c for c in current.cycles if c.number == cycle_number)
            if current.status != TaskStatus.ACTIVE or current_cycle.status != CycleStatus.ACTIVE:
                raise TaskStateConflict("Investigation or cycle stopped during execution")

        def checkpoint() -> None:
            # Release the lock before adapter work so pause can proceed while it runs.
            try:
                guard()
            finally:
                self.session.rollback()

        def finish_failure(status: str) -> ResearchTask:
            self.session.rollback()
            # A manual outcome may have stopped this run. Never overwrite it.
            try:
                return research.record_cycle_outcome(
                    task_id,
                    cycle_number,
                    CycleOutcomeCreate(
                        status="failed" if status == "failed" else "blocked",
                        result_summary=(
                            "Agent run stopped; review retained evidence and objectives."
                        ),
                        evidence_ids=evidence_ids,
                        claim_ids=claim_ids,
                        unresolved_objectives=list(cycle.objectives),
                        attempted_objectives=[cycle.objectives[index] for index in results],
                        objective_results=list(results.values()),
                    ),
                )
            except TaskStateConflict:
                current = repository.get(task_id)
                current_cycle = next(item for item in current.cycles if item.number == cycle_number)
                if current_cycle.status not in {
                    CycleStatus.COMPLETED,
                    CycleStatus.BLOCKED,
                    CycleStatus.FAILED,
                }:
                    # A rejected recovery write is not a successfully recorded outcome.
                    raise
                return current

        try:
            checkpoint()
            policy.authorize_discovery()
            agents = network.discover(limit=policy.max_agents)
            if not agents:
                raise AgentNetworkError("No agents available")
            for question_number, agent in enumerate(agents, start=1):
                checkpoint()
                policy.authorize_question(question_number)
                question = AgentQuestion(
                    task_id=task_id,
                    agent_id=agent.id,
                    question="\n\n".join(selected_objectives),
                )
                source = AgentEvidenceService(
                    self.session,
                    network,
                    before_write=guard,
                    after_write=lambda source: progress.source(source, selected_indices),
                ).ask_and_record(question, before_ask=mark_attempted)
                if source.id not in evidence_ids:
                    evidence_ids.append(source.id)
                for result in results.values():
                    if source.id not in result.source_ids:
                        result.source_ids.append(source.id)
                checkpoint()
                claims = ClaimExtractionService(self.session).extract_for_source(
                    task_id,
                    source.id,
                    before_write=guard,
                    after_write=lambda claims: progress.claims(claims, selected_indices),
                )
                claim_ids.extend(claim.id for claim in claims if claim.id not in claim_ids)
                for result in results.values():
                    result.claim_ids.extend(
                        claim.id for claim in claims if claim.id not in result.claim_ids
                    )
            return research.record_cycle_outcome(
                task_id,
                cycle_number,
                CycleOutcomeCreate(
                    status="completed",
                    result_summary=(
                        f"Collected {len(evidence_ids)} agent observation(s) and "
                        f"extracted {len(claim_ids)} unverified claim(s)."
                    ),
                    evidence_ids=evidence_ids,
                    claim_ids=claim_ids,
                    unresolved_objectives=list(cycle.objectives),
                    attempted_objectives=[cycle.objectives[index] for index in results],
                    objective_results=list(results.values()),
                ),
                require_active_task=True,
            )
        except (AgentNetworkError, BoundaryViolation, ValueError, TaskStateConflict):
            return finish_failure("blocked")
        except Exception as error:
            # Unexpected failures remain errors, but do not strand an active cycle
            # when the database is available for the recovery transaction.
            try:
                finish_failure("failed")
            except Exception:
                self.session.rollback()
                error.add_note("Cycle outcome recovery failed; operator recovery is required.")
            raise
