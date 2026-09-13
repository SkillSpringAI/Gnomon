"""Compare agent observations without promoting them into knowledge."""

from collections.abc import Sequence

from research_agent.domain.agent_comparison import (
    AgentObservationComparison,
    ObservationComparison,
    ObservationRelation,
)
from research_agent.domain.agents import AgentObservation, ObservationStance


class AgentComparisonService:
    """Use only explicit, deterministic signals from bounded observations."""

    def compare(
        self, observations: Sequence[AgentObservation]
    ) -> AgentObservationComparison:
        omitted = max(0, len(observations) - 100)
        observations = sorted(
            observations, key=lambda item: (item.observed_at, str(item.id))
        )[-100:]

        comparisons: list[ObservationComparison] = []
        for index, left in enumerate(observations):
            for right in observations[index + 1 :]:
                comparisons.append(
                    ObservationComparison(
                        left_id=left.id,
                        right_id=right.id,
                        relation=self._relation(left, right),
                    )
                )
        distinct_agents = {
            (observation.agent.network, observation.agent.platform_agent_id)
            for observation in observations
        }
        return AgentObservationComparison(
            observation_ids=[observation.id for observation in observations],
            comparisons=comparisons,
            distinct_agent_count=len(distinct_agents),
            omitted_observation_count=omitted,
        )

    @staticmethod
    def _relation(left: AgentObservation, right: AgentObservation) -> ObservationRelation:
        if left.duplicate_of == right.id or right.duplicate_of == left.id:
            return ObservationRelation.DUPLICATE
        if left.subject_id is None or left.subject_id != right.subject_id:
            return ObservationRelation.UNRELATED
        if left.content == right.content:
            return ObservationRelation.AGREEMENT
        if {left.stance, right.stance} == {
            ObservationStance.SUPPORTS,
            ObservationStance.CONTRADICTS,
        }:
            return ObservationRelation.CONTRADICTION
        return ObservationRelation.UNRELATED
