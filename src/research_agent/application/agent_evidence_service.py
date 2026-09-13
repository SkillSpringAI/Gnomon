"""Acquire agent observations and route them through ordinary evidence storage."""

from collections.abc import Callable
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from research_agent.application.audit_service import AuditService
from research_agent.application.evidence_service import EvidenceService
from research_agent.domain.agents import AgentObservation, AgentQuestion
from research_agent.domain.events import EventPayload, EventType
from research_agent.domain.research import SourceCreate, SourceResponse, SourceType
from research_agent.ports.agent_network import AgentNetwork, AgentNetworkError


class AgentEvidenceService:
    """Keep external agents below the evidence and audit boundaries."""

    def __init__(
        self,
        session: Session,
        network: AgentNetwork,
        operation_id: UUID | None = None,
        *,
        before_write: Callable[[], None] | None = None,
    ) -> None:
        self.session = session
        self.network = network
        self.operation_id = operation_id or uuid4()
        self.before_write = before_write

    def ask_and_record(
        self, question: AgentQuestion, *, before_ask: Callable[[], None] | None = None
    ) -> SourceResponse:
        evidence = EvidenceService(self.session, self.operation_id)
        evidence.require_task(question.task_id)
        try:
            if before_ask is not None:
                before_ask()
            observation = self.network.ask(question)
            return self._record_observation(question, observation)
        except AgentNetworkError:
            AuditService(self.session).record_failure(
                question.task_id,
                EventType.AGENT_OBSERVATION_FAILED,
                EventPayload(
                    operation_id=self.operation_id,
                    actor="agent_network",
                    reason="agent_network_failed",
                    result="failed",
                ),
            )
            raise

    def _record_observation(
        self, question: AgentQuestion, observation: AgentObservation
    ) -> SourceResponse:
        if observation.question_id != question.id or observation.agent.id != question.agent_id:
            raise ValueError("Agent observation does not match the requested question")
        source = SourceCreate(
            source_type=SourceType.AGENT_MESSAGE,
            title=f"Agent observation from {observation.agent.display_name}",
            uri=(
                f"agent://{observation.agent.network}/"
                f"{observation.agent.platform_agent_id}/{observation.id}"
            ),
            publisher=observation.agent.display_name,
            content=observation.content,
            source_metadata={
                "agent_id": str(observation.agent.id),
                "network": observation.agent.network,
                "platform_agent_id": observation.agent.platform_agent_id,
                "question_id": str(observation.question_id),
                "observation_id": str(observation.id),
                "subject_id": str(question.subject_id),
                "stance": observation.stance.value,
                "duplicate_of": str(observation.duplicate_of)
                if observation.duplicate_of is not None
                else "",
            },
        )
        return EvidenceService(self.session, self.operation_id).create_source(
            question.task_id,
            source,
            audit_event=EventType.AGENT_OBSERVATION_RECORDED,
            audit_actor="agent_network",
            provenance=[observation.agent.id, question.id],
            before_write=self.before_write,
        )
