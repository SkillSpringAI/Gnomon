from uuid import uuid4

import pytest

from research_agent.adapters.agents.fake import FakeAgentNetwork, FakeScenario
from research_agent.domain.agents import AgentQuestion
from research_agent.ports.agent_network import AgentNetworkError
from research_agent.security.boundaries import BoundaryViolation


def question(network: FakeAgentNetwork) -> AgentQuestion:
    agent = network.discover(limit=1)[0]
    return AgentQuestion(task_id=uuid4(), agent_id=agent.id, question="What should we verify next?")


def test_discovery_is_bounded_and_platform_neutral() -> None:
    network = FakeAgentNetwork()
    assert len(network.discover(limit=1)) == 1
    assert network.discover(limit=1)[0].network == "fake"
    with pytest.raises(BoundaryViolation):
        network.discover(limit=21)


@pytest.mark.parametrize("scenario", list(FakeScenario))
def test_adversarial_scenarios_are_data_or_bounded_failures(scenario: FakeScenario) -> None:
    network = FakeAgentNetwork(scenario)
    if scenario in {FakeScenario.UNRESPONSIVE, FakeScenario.RATE_LIMITED}:
        with pytest.raises(AgentNetworkError):
            network.ask(question(network))
        return
    observation = network.ask(question(network))
    assert observation.scenario == scenario.value
    assert observation.agent.network == "fake"
    assert observation.content


def test_duplicate_scenario_is_explicit_and_does_not_become_authority() -> None:
    network = FakeAgentNetwork(FakeScenario.DUPLICATE)
    first = network.ask(question(network))
    second = network.ask(question(network))
    assert first.duplicate_of is None
    assert second.duplicate_of == first.id
    assert first.model_dump() != second.model_dump()
