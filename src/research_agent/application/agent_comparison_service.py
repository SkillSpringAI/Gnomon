"""Compare agent observations without promoting them into knowledge."""

from collections.abc import Sequence

from research_agent.domain.agent_comparison import (
    AgentObservationComparison,
    ObservationComparison,
    ObservationRelation,
)
from research_agent.domain.agents import AgentObservation, ObservationStance
from research_agent.security.boundaries import BoundaryViolation


class AgentComparisonService:
    """Use only explicit, deterministic signals from bounded observations."""

    def compare(
        self, observations: Sequence[AgentObservation]
    ) -> AgentObservationComparison:
        if len(observations) > 100:
            raise BoundaryViolation("Agent comparison is limited to 100 observations")
        if not observations:
            return AgentObservationComparison(
                observation_ids=[], comparisons=[], independent_agent_count=0
            )

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
        independent_agents = {
            (observation.agent.network, observation.agent.platform_agent_id)
            for observation in observations
        }
        return AgentObservationComparison(
            observation_ids=[observation.id for observation in observations],
            comparisons=comparisons,
            independent_agent_count=len(independent_agents),
        )

    @staticmethod
    def _relation(left: AgentObservation, right: AgentObservation) -> ObservationRelation:
        if left.duplicate_of == right.id or right.duplicate_of == left.id:
            return ObservationRelation.DUPLICATE
        if left.content == right.content:
            return ObservationRelation.AGREEMENT
        if {left.stance, right.stance} == {
            ObservationStance.SUPPORTS,
            ObservationStance.CONTRADICTS,
        }:
            return ObservationRelation.CONTRADICTION
        return ObservationRelation.UNRELATED
