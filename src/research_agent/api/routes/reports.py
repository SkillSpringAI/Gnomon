"""Read-only evidence-aware investigation reports."""

from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from research_agent.adapters.llm.bedrock_bearer_report import BedrockBearerReportDraftGenerator
from research_agent.adapters.llm.bedrock_report import BedrockReportDraftGenerator
from research_agent.adapters.llm.rule_based_report import RuleBasedReportDraftGenerator
from research_agent.api.routes.provider import provider_sessions
from research_agent.application.audit_service import AuditService
from research_agent.application.provider_budget_service import (
    ProviderAttemptConflict,
    ProviderBudgetExceeded,
    ProviderBudgetService,
)
from research_agent.application.report_generation_service import (
    ReportGenerationError,
    ReportGenerationService,
    ReportGenerationUncertain,
)
from research_agent.application.report_service import ReportService
from research_agent.application.research_service import ResearchTaskNotFound
from research_agent.application.security_capability import (
    SecurityCapability,
    require_capability,
)
from research_agent.application.snapshot_service import SnapshotService
from research_agent.config.settings import get_settings
from research_agent.domain.events import EventPayload, EventType
from research_agent.domain.report import InvestigationReport, ReportDraft
from research_agent.persistence.database import get_session
from research_agent.persistence.models import ReportGenerationAttemptRecord, ResearchTaskRecord

router = APIRouter(prefix="/investigations", tags=["reports"])


@router.get("/{task_id}/workspace", response_class=HTMLResponse, include_in_schema=False)
def investigation_workspace(
    task_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> str:
    """Serve a credential-free browser workspace for one investigation."""
    task_exists = session.scalar(
        select(ResearchTaskRecord.id).where(ResearchTaskRecord.id == task_id)
    )
    if task_exists is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    template = Path(__file__).with_name("workspace.html").read_text(encoding="utf-8")
    return template.replace("__TASK_ID__", str(task_id))


def get_report_generator(
    request: Request,
    task_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> ReportGenerationService:
    # Reject missing tasks before credential discovery or optional provider construction.
    exists = session.scalar(select(ResearchTaskRecord.id).where(ResearchTaskRecord.id == task_id))
    session.rollback()
    if exists is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    require_capability(session, SecurityCapability.PROVIDER_DISPATCH)
    settings = get_settings()
    if settings.llm_provider.lower() == "bedrock":
        session_token = provider_sessions.get(request.cookies.get("provider_session"))
        if session_token:
            return ReportGenerationService(
                BedrockBearerReportDraftGenerator(
                    token=session_token,
                    model_id=settings.model_id,
                    region=settings.aws_region,
                    timeout_seconds=settings.llm_timeout_seconds,
                    max_output_tokens=settings.llm_max_output_tokens,
                )
            )
        return ReportGenerationService(
            BedrockReportDraftGenerator(
                model_id=settings.model_id,
                region=settings.aws_region,
                timeout_seconds=settings.llm_timeout_seconds,
                max_output_tokens=settings.llm_max_output_tokens,
            )
        )
    return ReportGenerationService(RuleBasedReportDraftGenerator())


@router.get("/{task_id}/report", response_model=InvestigationReport)
def get_report(
    task_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> InvestigationReport:
    try:
        session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        return ReportService().build(SnapshotService(session).get(task_id))
    except ResearchTaskNotFound as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.post("/{task_id}/report/draft", response_model=ReportDraft)
def generate_report_draft(
    task_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    generator: Annotated[ReportGenerationService, Depends(get_report_generator)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ReportDraft:
    """Generate a local draft from the current structured report without persistence."""
    try:
        operation_id = UUID(idempotency_key) if idempotency_key else uuid4()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Idempotency-Key must be a UUID") from exc
    settings = get_settings()
    try:
        require_capability(session, SecurityCapability.PROVIDER_DISPATCH)
        ProviderBudgetService(session).reserve(
            task_id,
            operation_id,
            settings.llm_max_drafts_per_task,
            settings.llm_timeout_seconds,
        )
        session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        report = ReportService().build(SnapshotService(session).get(task_id))
        # Fully materialized read model: no transaction spans provider execution.
        session.rollback()
        if len(report.model_dump_json()) > settings.llm_max_report_chars:
            ProviderBudgetService(session).finish(
                operation_id,
                "FAILED",
                "report_input_too_large",
                payload=EventPayload(
                    operation_id=operation_id,
                    reason="report_input_too_large",
                ),
            )
            raise HTTPException(status_code=413, detail="Report input exceeds configured limit")
        ProviderBudgetService(session).dispatch(operation_id)
        started_at = monotonic()
        draft = generator.generate(report)
        latency_ms = max(0, round((monotonic() - started_at) * 1000))
        ProviderBudgetService(session).finish(
            operation_id,
            "SUCCEEDED",
            payload=EventPayload(
                operation_id=operation_id,
                provider=draft.provider,
                model=draft.model,
                claim_count=len(draft.cited_claim_ids),
                input_tokens=draft.usage.input_tokens if draft.usage else None,
                output_tokens=draft.usage.output_tokens if draft.usage else None,
                total_tokens=draft.usage.total_tokens if draft.usage else None,
                latency_ms=latency_ms,
            ),
        )
        return draft
    except ResearchTaskNotFound as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ReportGenerationUncertain as exc:
        ProviderBudgetService(session).finish(
            operation_id,
            "UNKNOWN",
            "provider_outcome_unknown",
            payload=EventPayload(operation_id=operation_id, reason="provider_outcome_unknown"),
        )
        raise HTTPException(status_code=502, detail="Provider outcome is unknown") from exc
    except ReportGenerationError as exc:
        ProviderBudgetService(session).finish(
            operation_id,
            "FAILED",
            "report_generation_failed",
            payload=EventPayload(
                operation_id=operation_id,
                reason="report_generation_failed",
            ),
        )
        raise HTTPException(status_code=502, detail="Report provider failed validation") from exc
    except ProviderBudgetExceeded as exc:
        session.rollback()
        AuditService(session).record_failure(
            task_id,
            EventType.REPORT_DRAFT_FAILED,
            EventPayload(operation_id=operation_id, reason="report_budget_exceeded"),
        )
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except ProviderAttemptConflict as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class ProviderAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    operation_id: UUID
    task_id: UUID
    status: str
    started_at: datetime
    expires_at: datetime
    finished_at: datetime | None
    error_reason: str | None


@router.get("/{task_id}/report/attempts/{operation_id}", response_model=ProviderAttemptResponse)
def get_provider_attempt(
    task_id: UUID,
    operation_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> ProviderAttemptResponse:
    attempt = session.get(ReportGenerationAttemptRecord, operation_id)
    if attempt is None or attempt.task_id != task_id:
        raise HTTPException(status_code=404, detail="Provider attempt not found")
    return ProviderAttemptResponse.model_validate(attempt)


@router.post("/{task_id}/report/attempts/{operation_id}/recover", status_code=204)
def recover_provider_attempt(
    task_id: UUID,
    operation_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> None:
    """Local operator records uncertainty; this never releases provider capacity."""
    get_provider_attempt(task_id, operation_id, session)
    session.rollback()
    try:
        ProviderBudgetService(session).recover(task_id, operation_id)
    except ProviderAttemptConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
