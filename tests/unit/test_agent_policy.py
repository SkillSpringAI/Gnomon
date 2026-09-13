import pytest

from research_agent.security.agent_policy import AgentNetworkCapability, AgentRunPolicy
from research_agent.security.boundaries import BoundaryViolation


def test_default_policy_allows_read_only_capabilities() -> None:
    policy = AgentRunPolicy(max_agents=2)
    policy.authorize_discovery()
    policy.authorize_question(1)
    policy.authorize_question(2)
    with pytest.raises(BoundaryViolation):
        policy.authorize(AgentNetworkCapability.SEND_MESSAGE)


def test_policy_enforces_agent_and_question_budgets() -> None:
    with pytest.raises(ValueError):
        AgentRunPolicy(max_agents=3)
    policy = AgentRunPolicy(max_agents=1)
    with pytest.raises(ValueError):
        policy.authorize_question(2)

