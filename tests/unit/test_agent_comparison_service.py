from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from research_agent.application.agent_comparison_service import AgentComparisonService
from research_agent.domain.agent_comparison import ObservationRelation
from research_agent.domain.agents import AgentIdentity, AgentObservation, ObservationStance


def observation(
    content: str,
    *,
    platform_id: str = "agent-1",
    stance: ObservationStance = ObservationStance.UNKNOWN,
    duplicate_of=None,
    subject_id=None,
):
    return AgentObservation(
        question_id=uuid4(),
        subject_id=subject_id,
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


def test_comparison_classifies_relationships_and_counts_distinct_agents() -> None:
    subject_id = uuid4()
    first = observation(
        "A source should be reviewed.", stance=ObservationStance.SUPPORTS, subject_id=subject_id
    )
    duplicate = observation(
        "A source should be reviewed.",
        platform_id="agent-2",
        stance=ObservationStance.SUPPORTS,
        subject_id=subject_id,
    )
    duplicate = duplicate.model_copy(update={"duplicate_of": first.id})
    contradiction = observation(
        "The evidence conflicts with that premise.",
        platform_id="agent-3",
        stance=ObservationStance.CONTRADICTS,
        subject_id=subject_id,
    )
    result = AgentComparisonService().compare([first, duplicate, contradiction])
    relations = {
        frozenset((item.left_id, item.right_id)): item.relation for item in result.comparisons
    }
    assert relations[frozenset((first.id, duplicate.id))] == ObservationRelation.DUPLICATE
    assert relations[frozenset((first.id, contradiction.id))] == ObservationRelation.CONTRADICTION
    assert relations[frozenset((duplicate.id, contradiction.id))] == (
        ObservationRelation.CONTRADICTION
    )
    assert result.distinct_agent_count == 3
    assert "do not establish truth" in result.note


def test_comparison_is_bounded() -> None:
    items = [
        observation(str(index), platform_id=str(index)).model_copy(update={
            "observed_at": datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=index)
        }) for index in range(101)
    ]
    result = AgentComparisonService().compare(items)
    assert result.omitted_observation_count == 1
    assert result.observation_ids == [item.id for item in items[1:]]
    assert len(result.comparisons) == 4950
    assert result.distinct_agent_count == 100
    assert result == AgentComparisonService().compare(list(reversed(items)))


@pytest.mark.parametrize("unknown", [False, True])
def test_opposite_stances_require_known_matching_subject(unknown):
    first = observation("Supports A", stance=ObservationStance.SUPPORTS, subject_id=uuid4())
    second = observation(
        "Contradicts B", stance=ObservationStance.CONTRADICTS,
        subject_id=None if unknown else uuid4(),
    )
    result = AgentComparisonService().compare([first, second])
    assert result.comparisons[0].relation == ObservationRelation.UNRELATED


def test_identical_text_is_not_agreement_across_subjects():
    first = observation("Yes", subject_id=uuid4())
    second = observation("Yes", subject_id=uuid4())
    assert AgentComparisonService().compare([first, second]).comparisons[0].relation == (
        ObservationRelation.UNRELATED
    )
