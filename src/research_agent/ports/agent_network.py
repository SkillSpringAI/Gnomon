"""Replaceable, read-only agent-network boundary."""

from typing import Protocol

from research_agent.domain.agents import AgentIdentity, AgentObservation, AgentQuestion


class AgentNetworkError(RuntimeError):
    """A bounded network operation could not produce an observation."""


class AgentNetwork(Protocol):
    def discover(self, *, limit: int) -> list[AgentIdentity]:
        """Return at most ``limit`` observed identities."""

    def ask(self, question: AgentQuestion) -> AgentObservation:
        """Ask one agent; returned content is always untrusted data."""

