"""Explicit capability policy for replaceable agent-network adapters."""

from enum import StrEnum

from research_agent.security.boundaries import require_capability


class AgentNetworkCapability(StrEnum):
    DISCOVER = "agent.discover"
    ASK = "agent.ask"
    SEND_MESSAGE = "agent.send_message"


class AgentRunPolicy:
    """Read-only default policy with an explicit per-run request budget."""

    def __init__(self, *, max_agents: int, max_questions: int | None = None) -> None:
        if not 1 <= max_agents <= 2:
            raise ValueError("Agent runs may select between 1 and 2 agents")
        question_limit = max_questions if max_questions is not None else max_agents
        if not 1 <= question_limit <= max_agents:
            raise ValueError("Question budget must be between 1 and the selected agent count")
        self.max_agents = max_agents
        self.max_questions = question_limit
        self._allowed = {
            AgentNetworkCapability.DISCOVER.value,
            AgentNetworkCapability.ASK.value,
        }

    def authorize(self, capability: AgentNetworkCapability) -> None:
        require_capability(capability.value, self._allowed)

    def authorize_discovery(self) -> None:
        self.authorize(AgentNetworkCapability.DISCOVER)

    def authorize_question(self, question_number: int) -> None:
        self.authorize(AgentNetworkCapability.ASK)
        if not 1 <= question_number <= self.max_questions:
            raise ValueError("Agent question budget exhausted")

