"""Provider limits and missing-task errors through real application composition."""

from uuid import uuid4

import pytest
from test_provider_lifecycle import provider_task  # noqa: F401

from research_agent.config.settings import get_settings
from research_agent.persistence.database import SessionFactory
from research_agent.persistence.models import ReportGenerationAttemptRecord


@pytest.mark.parametrize("mode", ["standard", "session"])
@pytest.mark.parametrize("tokens", [1, 100])
def test_configured_token_limit_reaches_both_transports(request, monkeypatch, mode, tokens):
    _, client, task_id = request.getfixturevalue("provider_task")
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    monkeypatch.setenv("LLM_MAX_OUTPUT_TOKENS", str(tokens))
    get_settings.cache_clear()
    calls = []
    payload = {
        "output": {
            "message": {
                "content": [
                    {
                        "text": (
                            '{"content":"A draft","cited_source_ids":[],'
                            '"cited_claim_ids":[],"limitations":[]}'
                        )
                    }
                ]
            }
        }
    }

    if mode == "standard":
        import boto3

        class Bedrock:
            def converse(self, **request):
                calls.append(request)
                return payload

        monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: Bedrock())
    else:
        import httpx

        def post(url, **request):
            calls.append(request["json"])
            return httpx.Response(200, json=payload, request=httpx.Request("POST", url))

        monkeypatch.setattr("research_agent.adapters.llm.bedrock_bearer_report.httpx.post", post)
        response = client.post("/provider/session", json={"bearer_token": "test-ephemeral-token"})
        assert response.status_code == 201, response.text
    try:
        response = client.post(f"/investigations/{task_id}/report/draft")
        assert response.status_code == 200, response.text
        assert len(calls) == 1 and calls[0]["inferenceConfig"]["maxTokens"] == tokens
        assert client.get("/provider/status").json()["max_output_tokens"] == tokens
    finally:
        client.delete("/provider/session")


@pytest.mark.parametrize("mode", ["stub", "standard", "session"])
def test_unknown_task_returns_404_before_provider_construction(request, monkeypatch, mode):
    _, client, _ = request.getfixturevalue("provider_task")
    task_id = uuid4()
    monkeypatch.setenv("LLM_PROVIDER", "stub" if mode == "stub" else "bedrock")
    get_settings.cache_clear()

    def unexpected(*args, **kwargs):
        raise AssertionError("Missing task must not construct a provider")

    for name in (
        "BedrockReportDraftGenerator",
        "BedrockBearerReportDraftGenerator",
        "RuleBasedReportDraftGenerator",
    ):
        monkeypatch.setattr(f"research_agent.api.routes.reports.{name}", unexpected)
    if mode == "session":
        assert (
            client.post("/provider/session", json={"bearer_token": "test-token"}).status_code == 201
        )
    try:
        response = client.post(f"/investigations/{task_id}/report/draft")
        assert response.status_code == 404, response.text
        with SessionFactory() as session:
            assert (
                session.query(ReportGenerationAttemptRecord).filter_by(task_id=task_id).all() == []
            )
    finally:
        client.delete("/provider/session")
