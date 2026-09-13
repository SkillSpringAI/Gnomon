from uuid import uuid4

import pytest

from research_agent.application.agent_comparison_service import AgentComparisonService
from research_agent.domain.agent_comparison import ObservationRelation
from research_agent.domain.agents import AgentIdentity, AgentObservation, ObservationStance
from research_agent.security.boundaries import BoundaryViolation


def observation(
    content: str,
    *,
    platform_id: str = "agent-1",
    stance: ObservationStance = ObservationStance.UNKNOWN,
    duplicate_of=None,
):
    return AgentObservation(
        question_id=uuid4(),
        agent=AgentIdentity(
            network="fake",
            platform_agent_id=platform_id,
            display_name=platform_id,
        ),
        content=content,
        scenario="test",
        stance=stance,
        duplicate_of=duplicate_of,
    )


def test_comparison_classifies_relationships_and_counts_independent_agents() -> None:
    first = observation(
        "A source should be reviewed.", stance=ObservationStance.SUPPORTS
    )
    duplicate = observation(
        "A source should be reviewed.",
        platform_id="agent-2",
        stance=ObservationStance.SUPPORTS,
    )
    duplicate = duplicate.model_copy(update={"duplicate_of": first.id})
    contradiction = observation(
        "The evidence conflicts with that premise.",
        platform_id="agent-3",
        stance=ObservationStance.CONTRADICTS,
    )
    result = AgentComparisonService().compare([first, duplicate, contradiction])
    relations = [item.relation for item in result.comparisons]
    assert relations == [
        ObservationRelation.DUPLICATE,
        ObservationRelation.CONTRADICTION,
        ObservationRelation.CONTRADICTION,
    ]
    assert result.independent_agent_count == 3
    assert "do not establish truth" in result.note


def test_comparison_is_bounded() -> None:
    items = [observation(str(index), platform_id=str(index)) for index in range(101)]
    with pytest.raises(BoundaryViolation):
        AgentComparisonService().compare(items)
