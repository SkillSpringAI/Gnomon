"""Persistence boundary for investigation tasks."""

from contextlib import AbstractContextManager
from typing import Protocol
from uuid import UUID

from research_agent.domain.research import ResearchTask
from research_agent.domain.snapshot import InvestigationSnapshot


class ResearchTaskRepository(Protocol):
    def save(self, task: ResearchTask) -> ResearchTask: ...
    def get(self, task_id: UUID) -> ResearchTask: ...

    def edit(self, task_id: UUID) -> AbstractContextManager[ResearchTask]: ...

    def planning_snapshot(self, task_id: UUID) -> InvestigationSnapshot: ...
