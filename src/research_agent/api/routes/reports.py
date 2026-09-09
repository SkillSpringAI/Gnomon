"""Read-only evidence-aware investigation reports."""

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from research_agent.adapters.llm.bedrock_bearer_report import BedrockBearerReportDraftGenerator
from research_agent.adapters.llm.bedrock_report import BedrockReportDraftGenerator
from research_agent.adapters.llm.rule_based_report import RuleBasedReportDraftGenerator
from research_agent.api.routes.provider import provider_sessions
from research_agent.application.audit_service import AuditService
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

router = APIRouter(prefix="/investigations", tags=["reports"])


@router.get("/{task_id}/workspace", response_class=HTMLResponse, include_in_schema=False)
def investigation_workspace(task_id: UUID) -> str:
    """Serve a credential-free browser workspace for one investigation."""
    task = str(task_id)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Investigation workspace</title>
  <style>
    :root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
    body {{ margin: 2rem auto; max-width: 58rem; padding: 0 1rem; }}
    button {{ cursor: pointer; padding: .55rem .8rem; }}
    pre {{ white-space: pre-wrap; border: 1px solid #8885; border-radius: .6rem; padding: 1rem; }}
    .muted {{ opacity: .75; }} .error {{ color: #b42318; }}
  </style>
</head>
<body>
  <h1 id="title">Investigation workspace</h1>
  <p id="summary" class="muted">Loading report…</p>
  <p><a href="/provider">Provider status</a></p>
  <button id="draft" type="button">Generate draft</button>
  <p id="message" class="muted" aria-live="polite"></p>
  <pre id="content" hidden></pre>
  <script>
    const taskId = {task!r};
    const title = document.getElementById('title');
    const summary = document.getElementById('summary');
    const message = document.getElementById('message');
    const content = document.getElementById('content');
    const escapeHtml = value => String(value).replace(/[&<>\"']/g, character => ({{
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '\"': '&quot;', "'": '&#39;'
    }}[character]));
    fetch(`/investigations/${{taskId}}/report`)
      .then(response => response.ok ? response.json() : Promise.reject(response.status))
      .then(report => {{
        title.textContent = report.title;
        summary.textContent = report.summary;
      }})
      .catch(() => {{
        message.textContent = 'Unable to load this investigation report.';
        message.className = 'error';
      }});
    document.getElementById('draft').addEventListener('click', () => {{
      message.textContent = 'Generating…';
      content.hidden = true;
      fetch(`/investigations/${{taskId}}/report/draft`, {{ method: 'POST' }})
        .then(response => response.ok ? response.json() : Promise.reject(response.status))
        .then(draft => {{
          content.textContent = draft.content;
          content.hidden = false;
          message.textContent = `${{draft.provider}} / ${{draft.model}}`;
        }})
        .catch(() => {{
          message.textContent = 'Draft generation failed or was rate-limited.';
          message.className = 'error';
        }});
    }});
  </script>
</body>
</html>"""


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
) -> ReportDraft:
    """Generate a local draft from the current structured report without persistence."""
    operation_id = uuid4()
    settings = get_settings()
    try:
        session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        report = ReportService().build(SnapshotService(session).get(task_id))
        audit = AuditService(session)
        if (
            audit.count_events(task_id, EventType.REPORT_DRAFT_GENERATED)
            >= settings.llm_max_drafts_per_task
        ):
            audit.record_failure(
                task_id,
                EventType.REPORT_DRAFT_FAILED,
                EventPayload(
                    operation_id=operation_id,
                    reason="report_budget_exceeded",
                ),
            )
            raise HTTPException(status_code=429, detail="Report draft limit reached")
        if len(report.model_dump_json()) > settings.llm_max_report_chars:
            audit.record_failure(
                task_id,
                EventType.REPORT_DRAFT_FAILED,
                EventPayload(
                    operation_id=operation_id,
                    reason="report_budget_exceeded",
                ),
            )
            raise HTTPException(status_code=413, detail="Report input exceeds configured limit")
        draft = generator.generate(report)
        audit.stage(
            task_id,
            EventType.REPORT_DRAFT_GENERATED,
            EventPayload(
                operation_id=operation_id,
                provider=draft.provider,
                model=draft.model,
                claim_count=len(draft.cited_claim_ids),
            ),
        )
        session.commit()
        return draft
    except ResearchTaskNotFound as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ReportGenerationError as exc:
        AuditService(session).record_failure(
            task_id,
            EventType.REPORT_DRAFT_FAILED,
            EventPayload(
                operation_id=operation_id,
                reason="report_generation_failed",
            ),
        )
        raise HTTPException(status_code=502, detail="Report provider failed validation") from exc
