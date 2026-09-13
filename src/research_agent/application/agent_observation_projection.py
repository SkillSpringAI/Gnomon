"""Reconstruct comparison inputs with source-resolvable provenance IDs."""

from uuid import UUID

from research_agent.domain.agents import AgentIdentity, AgentObservation, ObservationStance
from research_agent.domain.snapshot import InvestigationSnapshot


def agent_observations(snapshot: InvestigationSnapshot) -> list[AgentObservation]:
    """Translate network observation references to this snapshot's source IDs.

    Legacy records may recover observation identity from their generated URI, but
    missing subjects remain unknown. Ambiguous duplicate targets are not inferred.
    """
    observations: list[AgentObservation] = []
    identities: dict[tuple[str, UUID], list[UUID]] = {}
    for source in snapshot.sources:
        if source.source_type.value != "agent_message":
            continue
        metadata = source.source_metadata
        try:
            observation = AgentObservation(
                id=source.id,
                question_id=UUID(metadata["question_id"]),
                subject_id=UUID(metadata["subject_id"]) if metadata.get("subject_id") else None,
                agent=AgentIdentity(
                    id=UUID(metadata["agent_id"]),
                    network=metadata["network"],
                    platform_agent_id=metadata["platform_agent_id"],
                    display_name=source.publisher or "Unknown agent",
                ),
                content=source.content,
                observed_at=source.observed_at,
                scenario="persisted",
                stance=ObservationStance(metadata["stance"]),
                duplicate_of=(
                    UUID(metadata["duplicate_of"]) if metadata.get("duplicate_of") else None
                ),
            )
        except (KeyError, TypeError, ValueError):
            continue
        observations.append(observation)
        prefix = f"agent://{observation.agent.network}/{observation.agent.platform_agent_id}/"
        original_id = metadata.get("observation_id")
        if not original_id and source.uri and source.uri.startswith(prefix):
            original_id = source.uri[len(prefix):]
        try:
            if original_id:
                key = (observation.agent.network, UUID(original_id))
                identities.setdefault(key, []).append(source.id)
        except ValueError:
            pass

    result = []
    for observation in observations:
        targets = (
            identities.get((observation.agent.network, observation.duplicate_of), [])
            if observation.duplicate_of is not None else []
        )
        duplicate = targets[0] if len(targets) == 1 and targets[0] != observation.id else None
        result.append(observation.model_copy(update={"duplicate_of": duplicate}))
    return result
