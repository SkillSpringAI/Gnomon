from uuid import uuid4

import pytest

from research_agent.adapters.agents.fake import FakeAgentNetwork, FakeScenario
from research_agent.domain.agents import AgentQuestion
from research_agent.ports.agent_network import AgentNetworkError


def test_agent_service_requires_matching_agent_identity() -> None:
    network = FakeAgentNetwork()
    agent = network.discover(limit=1)[0]
    question = AgentQuestion(task_id=uuid4(), agent_id=agent.id, question="Verify this.")
    observation = network.ask(question)
    assert observation.question_id == question.id
    assert observation.agent.id == question.agent_id


def test_unresponsive_network_is_a_bounded_failure() -> None:
    network = FakeAgentNetwork(FakeScenario.UNRESPONSIVE)
    with pytest.raises(AgentNetworkError):
        network.ask(
            AgentQuestion(task_id=uuid4(), agent_id=uuid4(), question="Return an observation.")
        )
