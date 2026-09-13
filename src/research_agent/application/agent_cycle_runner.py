"""Run one bounded local agent-research cycle end to end."""

from uuid import UUID

from sqlalchemy.orm import Session

from research_agent.adapters.agents.fake import FakeAgentNetwork, FakeScenario
from research_agent.application.agent_evidence_service import AgentEvidenceService
from research_agent.application.claim_extraction_service import ClaimExtractionService
from research_agent.application.research_service import ResearchService
from research_agent.domain.agents import AgentQuestion
from research_agent.domain.research import CycleOutcomeCreate, ResearchTask
from research_agent.persistence.repositories import SqlAlchemyResearchTaskRepository


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
    ) -> ResearchTask:
        network = FakeAgentNetwork(scenario)
        repository = SqlAlchemyResearchTaskRepository(self.session)
        research = ResearchService(repository)
        task = research.start_cycle(task_id, cycle_number)
        cycle = next(cycle for cycle in task.cycles if cycle.number == cycle_number)
        objective = cycle.objectives[0]
        agents = network.discover(limit=max_agents)
        evidence_ids: list[UUID] = []
        claim_ids: list[UUID] = []
        try:
            for agent in agents:
                question = AgentQuestion(
                    task_id=task_id,
                    agent_id=agent.id,
                    question=objective,
                )
                source = AgentEvidenceService(self.session, network).ask_and_record(question)
                evidence_ids.append(source.id)
                claims = ClaimExtractionService(self.session).extract_for_source(task_id, source.id)
                claim_ids.extend(claim.id for claim in claims)
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
                ),
            )
        except Exception:
            # Preserve the bounded failure as a cycle outcome while retaining no
            # provider/agent exception text in the persisted summary.
            return research.record_cycle_outcome(
                task_id,
                cycle_number,
                CycleOutcomeCreate(
                    status="blocked",
                    result_summary="Agent acquisition did not complete within the bounded run.",
                    evidence_ids=evidence_ids,
                    claim_ids=claim_ids,
                    unresolved_objectives=[objective],
                ),
            )

