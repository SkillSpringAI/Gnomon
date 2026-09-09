"""Safe provider configuration status endpoint."""

import os
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse

from research_agent.application.provider_session import ProviderSessionStore
from research_agent.config.settings import get_settings
from research_agent.domain.provider import ProviderSessionCreate, ProviderStatusResponse

router = APIRouter(prefix="/provider", tags=["provider"])
provider_sessions = ProviderSessionStore()


@router.get("", response_class=HTMLResponse, include_in_schema=False)
def provider_panel() -> str:
    """Serve a small credential-safe provider status panel."""
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Research Agent Provider</title>
  <style>
    :root { color-scheme: light dark; font-family: system-ui, sans-serif; }
    body { margin: 2rem auto; max-width: 42rem; padding: 0 1rem; }
    .card { border: 1px solid #8885; border-radius: .8rem; padding: 1.2rem; }
    dl { display: grid; grid-template-columns: 12rem 1fr; gap: .55rem 1rem; }
    dt { font-weight: 650; } dd { margin: 0; overflow-wrap: anywhere; }
    .ready { color: #187a3d; } .error { color: #b42318; }
    small { opacity: .75; }
  </style>
</head>
<body>
  <h1>Provider status</h1>
  <div class="card" id="panel" aria-live="polite">Loading…</div>
  <p><small>This panel displays configuration metadata only.
    Credential values are never returned.</small></p>
  <script>
    const panel = document.getElementById('panel');
    const escapeHtml = value => String(value).replace(/[&<>\"']/g, character => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '\"': '&quot;', "'": '&#39;'
    }[character]));
    fetch('/provider/status')
      .then(response => response.ok ? response.json() : Promise.reject(response.status))
      .then(status => {
        panel.innerHTML = `<p class="ready"><strong>Configuration loaded</strong></p>
          <dl>
            <dt>Provider</dt><dd>${escapeHtml(status.provider)}</dd>
            <dt>Model</dt><dd>${escapeHtml(status.model_id)}</dd>
            <dt>Region</dt><dd>${escapeHtml(status.region)}</dd>
            <dt>Credential mode</dt><dd>${escapeHtml(status.credential_mode)}</dd>
            <dt>Max output tokens</dt><dd>${escapeHtml(status.max_output_tokens)}</dd>
            <dt>Max report chars</dt><dd>${escapeHtml(status.max_report_chars)}</dd>
            <dt>Drafts per task</dt><dd>${escapeHtml(status.max_drafts_per_task)}</dd>
          </dl>`;
      })
      .catch(error => {
        panel.innerHTML = `<p class="error"><strong>Unable to load provider status</strong></p>
          <p>Request failed safely; no credential details are displayed.</p>`;
      });
  </script>
</body>
</html>"""


@router.get("/status", response_model=ProviderStatusResponse)
def provider_status(request: Request) -> ProviderStatusResponse:
    """Return provider settings without credentials or a network call."""
    settings = get_settings()
    if settings.llm_provider.lower() != "bedrock":
        mode: Literal[
            "stub", "bearer_token", "session_bearer_token", "aws_default_chain"
        ] = "stub"
    elif provider_sessions.get(request.cookies.get("provider_session")):
        mode = "session_bearer_token"
    elif os.getenv("AWS_BEARER_TOKEN_BEDROCK"):
        mode = "bearer_token"
    else:
        mode = "aws_default_chain"
    return ProviderStatusResponse(
        provider=settings.llm_provider,
        model_id=settings.model_id,
        region=settings.aws_region,
        credential_mode=mode,
        max_output_tokens=settings.llm_max_output_tokens,
        max_report_chars=settings.llm_max_report_chars,
        max_drafts_per_task=settings.llm_max_drafts_per_task,
    )


@router.post("/session", status_code=status.HTTP_201_CREATED)
def create_provider_session(
    payload: ProviderSessionCreate,
    request: Request,
    response: Response,
) -> dict[str, str]:
    """Accept a bearer token only from loopback and keep it in memory until expiry."""
    if request.client is None or request.client.host not in {
        "127.0.0.1",
        "::1",
        "localhost",
        "testclient",
    }:
        raise HTTPException(status_code=403, detail="Provider sessions are local-only")
    session_id, expires_at = provider_sessions.create(
        payload.bearer_token.get_secret_value(), payload.ttl_seconds
    )
    response.set_cookie(
        "provider_session",
        session_id,
        max_age=payload.ttl_seconds,
        httponly=True,
        samesite="strict",
    )
    return {"status": "active", "expires_at": expires_at.isoformat()}


@router.delete("/session", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider_session(request: Request, response: Response) -> None:
    """Forget the local provider token and expire the session cookie."""
    provider_sessions.delete(request.cookies.get("provider_session"))
    response.delete_cookie("provider_session")
