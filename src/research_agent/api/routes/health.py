"""Health and readiness endpoints."""

from typing import Final

from fastapi import APIRouter

from research_agent import __version__
from research_agent.config.settings import get_settings

router: Final = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    """Return a process-level health response."""
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": __version__,
        "environment": settings.environment,
    }
