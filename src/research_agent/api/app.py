"""FastAPI application factory and application instance."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from research_agent import __version__
from research_agent.api.routes.assessments import router as assessments_router
from research_agent.api.routes.events import router as events_router
from research_agent.api.routes.evidence import router as evidence_router
from research_agent.api.routes.health import router as health_router
from research_agent.api.routes.investigations import (
    get_research_service,
)
from research_agent.api.routes.investigations import (
    router as investigations_router,
)
from research_agent.api.routes.memory import router as memory_router
from research_agent.api.routes.provider import router as provider_router
from research_agent.api.routes.reports import router as reports_router
from research_agent.api.routes.snapshots import router as snapshots_router
from research_agent.api.routes.source_registry import router as source_registry_router
from research_agent.application.research_service import (
    InMemoryResearchTaskRepository,
    ResearchService,
)
from research_agent.config.settings import get_settings
from research_agent.domain.memory import MemoryConflict, MemoryDenied
from research_agent.persistence.repositories import SqlAlchemyResearchTaskRepository


def create_app(
    repository: InMemoryResearchTaskRepository | SqlAlchemyResearchTaskRepository | None = None,
) -> FastAPI:
    """Create the HTTP application."""
    settings = get_settings()
    if repository is None and settings.persistence_backend == "memory":
        repository = InMemoryResearchTaskRepository()
    application = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="A provenance-aware research intelligence agent.",
    )
    application.include_router(health_router)
    application.include_router(memory_router)

    @application.exception_handler(MemoryConflict)
    async def memory_conflict(request: Request, exc: MemoryConflict) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @application.exception_handler(MemoryDenied)
    async def memory_denied(request: Request, exc: MemoryDenied) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    application.include_router(events_router)
    application.include_router(investigations_router)
    application.include_router(evidence_router)
    application.include_router(assessments_router)
    application.include_router(source_registry_router)
    application.include_router(snapshots_router)
    application.include_router(reports_router)
    application.include_router(provider_router)
    if repository is not None:
        application.dependency_overrides[get_research_service] = lambda: ResearchService(repository)
    return application


app = create_app()
