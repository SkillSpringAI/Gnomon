"""Read-only PostgreSQL investigation snapshot endpoint."""

from collections.abc import Generator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from research_agent.application.research_service import ResearchTaskNotFound
from research_agent.application.snapshot_service import SnapshotService
from research_agent.domain.snapshot import InvestigationSnapshot
from research_agent.persistence.database import SessionFactory

router = APIRouter(prefix="/investigations", tags=["investigations"])


def get_snapshot_service() -> Generator[SnapshotService, None, None]:
    with SessionFactory() as session:
        # Keep the evidence chain consistent if writes occur between queries.
        session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        yield SnapshotService(session)


@router.get("/{task_id}/snapshot", response_model=InvestigationSnapshot)
def get_snapshot(
    task_id: UUID,
    service: Annotated[SnapshotService, Depends(get_snapshot_service)],
) -> InvestigationSnapshot:
    try:
        return service.get(task_id)
    except ResearchTaskNotFound as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
