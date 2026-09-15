"""Read-only evidence-aware investigation reports."""

from pathlib import Path
from time import monotonic
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
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
)
from research_agent.application.report_service import ReportService
from research_agent.application.research_service import ResearchTaskNotFound
from research_agent.application.snapshot_service import SnapshotService
from research_agent.config.settings import get_settings
from research_agent.domain.events import EventPayload, EventType
from research_agent.domain.report import InvestigationReport, ReportDraft
from research_agent.persistence.database import get_session
from research_agent.persistence.models import ResearchTaskRecord

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


def get_report_generator(request: Request) -> ReportGenerationService:
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
        ProviderBudgetService(session).reserve(
            task_id,
            operation_id,
            settings.llm_max_drafts_per_task,
            settings.llm_timeout_seconds,
        )
        ProviderBudgetService(session).dispatch(operation_id)
        session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        report = ReportService().build(SnapshotService(session).get(task_id))
        audit = AuditService(session)
        if len(report.model_dump_json()) > settings.llm_max_report_chars:
            ProviderBudgetService(session).finish(operation_id, "FAILED", "report_input_too_large")
            audit.record_failure(
                task_id,
                EventType.REPORT_DRAFT_FAILED,
                EventPayload(
                    operation_id=operation_id,
                    reason="report_input_too_large",
                ),
            )
            raise HTTPException(status_code=413, detail="Report input exceeds configured limit")
        started_at = monotonic()
        draft = generator.generate(report)
        latency_ms = max(0, round((monotonic() - started_at) * 1000))
        audit.stage(
            task_id,
            EventType.REPORT_DRAFT_GENERATED,
            EventPayload(
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
        session.commit()
        ProviderBudgetService(session).finish(operation_id, "SUCCEEDED")
        return draft
    except ResearchTaskNotFound as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ReportGenerationError as exc:
        ProviderBudgetService(session).finish(operation_id, "FAILED", "report_generation_failed")
        AuditService(session).record_failure(
            task_id,
            EventType.REPORT_DRAFT_FAILED,
            EventPayload(
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
