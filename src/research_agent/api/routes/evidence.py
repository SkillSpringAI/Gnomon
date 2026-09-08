"""Source and claim endpoints."""

from collections.abc import Generator
from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from research_agent.adapters.web.http import HttpSourceRetriever, SourceRetrievalError
from research_agent.application.audit_service import AuditService
from research_agent.application.claim_extraction_service import (
    ClaimExtractionService,
    SourceNotFound,
)
from research_agent.application.evidence_service import EvidenceService
from research_agent.application.research_service import ResearchTaskNotFound
from research_agent.application.source_registry import (
    SourceRegistryService,
    UntrustedSourceError,
)
from research_agent.config.settings import get_settings
from research_agent.domain.events import EventPayload, EventType
from research_agent.domain.research import (
    ClaimCreate,
    ClaimResponse,
    SourceCreate,
    SourceFetchRequest,
    SourceResponse,
)
from research_agent.persistence.database import SessionFactory
from research_agent.ports.retrieval import SourceTarget

router: Final = APIRouter(prefix="/investigations/{task_id}", tags=["evidence"])


def get_evidence_service() -> Generator[EvidenceService, None, None]:
    """Return a database-backed evidence service and close its session."""
    session = SessionFactory()
    try:
        yield EvidenceService(session)
    finally:
        session.close()


def get_source_registry() -> Generator[SourceRegistryService, None, None]:
    """Provide the trusted-source policy service."""
    session = SessionFactory()
    try:
        yield SourceRegistryService(session)
    finally:
        session.close()


def get_source_retriever(
    registry: Annotated[SourceRegistryService, Depends(get_source_registry)],
) -> Generator[HttpSourceRetriever, None, None]:
    """Check policy before the initial request and every redirect request."""
    retriever = HttpSourceRetriever(
        url_policy=registry.require_enabled if get_settings().require_trusted_sources else None,
    )
    try:
        yield retriever
    finally:
        retriever.client.close()


def get_claim_extraction_service() -> Generator[ClaimExtractionService, None, None]:
    """Provide the claim extraction service and close its session."""
    session = SessionFactory()
    try:
        yield ClaimExtractionService(session)
    finally:
        session.close()


@router.post("/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
def create_source(
    task_id: UUID,
    source: SourceCreate,
    service: Annotated[EvidenceService, Depends(get_evidence_service)],
) -> SourceResponse:
    """Store raw source evidence for an investigation."""
    try:
        return service.create_source(task_id, source)
    except ResearchTaskNotFound as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.post("/sources/fetch", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
def fetch_source(
    task_id: UUID,
    request: SourceFetchRequest,
    evidence_service: Annotated[EvidenceService, Depends(get_evidence_service)],
    retriever: Annotated[HttpSourceRetriever, Depends(get_source_retriever)],
) -> SourceResponse:
    """Fetch an approved HTTP(S) source and persist it as evidence."""
    try:
        evidence_service.require_task(task_id)
        retrieved = retriever.fetch(SourceTarget(uri=request.uri, source_type=request.source_type))
        return evidence_service.create_source_from_retrieval(
            task_id,
            retrieved,
            request.reliability_score,
            request.source_type,
        )
    except ResearchTaskNotFound as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except SourceRetrievalError as exc:
        AuditService(evidence_service.session).record_failure(
            task_id,
            EventType.RETRIEVAL_FAILED,
            EventPayload(operation_id=evidence_service.operation_id, reason="retrieval_rejected"),
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except UntrustedSourceError as exc:
        AuditService(evidence_service.session).record_failure(
            task_id,
            EventType.RETRIEVAL_FAILED,
            EventPayload(operation_id=evidence_service.operation_id, reason="domain_not_enabled"),
        )
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/claims", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
def create_claim(
    task_id: UUID,
    claim: ClaimCreate,
    service: Annotated[EvidenceService, Depends(get_evidence_service)],
) -> ClaimResponse:
    """Store a claim only when its provenance sources are valid."""
    try:
        return service.create_claim(task_id, claim)
    except ResearchTaskNotFound as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/sources/{source_id}/extract-claims", response_model=list[ClaimResponse])
def extract_claims(
    task_id: UUID,
    source_id: UUID,
    service: Annotated[ClaimExtractionService, Depends(get_claim_extraction_service)],
) -> list[ClaimResponse]:
    """Extract conservative, unverified claims from stored source content."""
    try:
        return service.extract_for_source(task_id, source_id)
    except (SourceNotFound, ResearchTaskNotFound) as exc:
        raise HTTPException(status_code=404, detail="Source not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
