"""Trusted source registry endpoints."""

from collections.abc import Generator
from typing import Annotated, Final

from fastapi import APIRouter, Depends, HTTPException, status

from research_agent.application.source_registry import SourceRegistryService, UntrustedSourceError
from research_agent.domain.research import TrustedSourceCreate, TrustedSourceResponse
from research_agent.persistence.database import SessionFactory

router: Final = APIRouter(prefix="/source-registry", tags=["source-registry"])


def get_registry_service() -> Generator[SourceRegistryService, None, None]:
    """Provide the source registry service and close its session."""
    session = SessionFactory()
    try:
        yield SourceRegistryService(session)
    finally:
        session.close()


@router.get("", response_model=list[TrustedSourceResponse])
def list_trusted_sources(
    service: Annotated[SourceRegistryService, Depends(get_registry_service)],
) -> list[TrustedSourceResponse]:
    """List registered source domains."""
    return service.list_sources()


@router.post("", response_model=TrustedSourceResponse, status_code=status.HTTP_201_CREATED)
def register_trusted_source(
    source: TrustedSourceCreate,
    service: Annotated[SourceRegistryService, Depends(get_registry_service)],
) -> TrustedSourceResponse:
    """Register a source domain for later review and enablement."""
    try:
        return service.register(source)
    except Exception as exc:
        raise HTTPException(status_code=409, detail="Source domain is already registered") from exc


@router.post("/{domain}/enable", response_model=TrustedSourceResponse)
def enable_trusted_source(
    domain: str,
    service: Annotated[SourceRegistryService, Depends(get_registry_service)],
) -> TrustedSourceResponse:
    """Enable a reviewed domain for retrieval during prototype operation."""
    try:
        return service.enable(domain)
    except UntrustedSourceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
