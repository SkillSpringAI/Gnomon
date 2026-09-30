"""Explicitly opted-in Bedrock configuration and one baseline generation."""

import json
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from dotenv import dotenv_values
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import select

from research_agent.adapters.llm.bedrock_report import BedrockReportDraftGenerator
from research_agent.api.app import create_app
from research_agent.api.routes.provider import provider_status
from research_agent.config.settings import get_settings
from research_agent.persistence.database import SessionFactory
from research_agent.persistence.models import ReportGenerationAttemptRecord, ResearchEventRecord

_LOCAL_FILE = Path(__file__).resolve().parents[2] / ".env.bedrock-live.local"
_SECRET_KEY = "AWS_BEARER_TOKEN_BEDROCK"
_LIVE_KEYS = frozenset(
    {
        "LLM_PROVIDER",
        "AWS_REGION",
        "MODEL_ID",
        "LLM_MAX_OUTPUT_TOKENS",
        "LLM_MAX_DRAFTS_PER_TASK",
        _SECRET_KEY,
    }
)
_AWS_CREDENTIAL_ENV_KEYS = (
    "AWS_PROFILE",
    "AWS_DEFAULT_PROFILE",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_SECURITY_TOKEN",
    "AWS_CREDENTIAL_EXPIRATION",
    "AWS_ACCOUNT_ID",
    "AWS_WEB_IDENTITY_TOKEN_FILE",
    "AWS_ROLE_ARN",
    "AWS_ROLE_SESSION_NAME",
    "AWS_CREDENTIAL_FILE",
    "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
    "AWS_CONTAINER_CREDENTIALS_FULL_URI",
    "AWS_CONTAINER_AUTHORIZATION_TOKEN",
    "AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE",
    "AWS_AUTH_SCHEME_PREFERENCE",
)
_AWS_ERROR_CODES = frozenset(
    {
        "AccessDeniedException",
        "IncompleteSignature",
        "InternalServerException",
        "InvalidClientTokenId",
        "ModelErrorException",
        "ModelNotReadyException",
        "ModelTimeoutException",
        "ResourceNotFoundException",
        "ServiceUnavailableException",
        "ThrottlingException",
        "ValidationException",
    }
)
_STOP_REASONS = frozenset(
    {
        "end_turn",
        "tool_use",
        "max_tokens",
        "stop_sequence",
        "guardrail_intervened",
        "content_filtered",
        "malformed_model_output",
        "malformed_tool_use",
        "model_context_window_exceeded",
    }
)


def _bounded_int(value: object, *, minimum: int = 0, maximum: int = 1_000_000_000) -> int | None:
    return value if type(value) is int and minimum <= value <= maximum else None


def _request_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return str(UUID(value))
    except ValueError:
        return None


def _exception_category(exc: Exception) -> str:
    try:
        from botocore.exceptions import (
            ClientError,
            ConnectTimeoutError,
            HTTPClientError,
            ParamValidationError,
            ReadTimeoutError,
        )
        from botocore.exceptions import ConnectionError as BotoConnectionError
    except ImportError:
        return "other"
    if isinstance(exc, ClientError):
        return "aws_service_error"
    if isinstance(exc, (ConnectTimeoutError, ReadTimeoutError)):
        return "timeout"
    if isinstance(exc, (BotoConnectionError, HTTPClientError)):
        return "connection_error"
    if isinstance(exc, ParamValidationError):
        return "local_parameter_error"
    return "other"


@dataclass(slots=True)
class _BedrockObservation:
    configured_region: str
    configured_model: str
    converse_returned: bool = False
    exception_category: str | None = None
    aws_error_code: str | None = None
    aws_request_id: str | None = None
    aws_http_status: int | None = None
    sdk_retry_attempts: int | None = None
    stop_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    service_latency_ms: int | None = None
    local_parse_succeeded: bool | None = None

    def _capture(self, response: object, *, error: bool) -> None:
        if not isinstance(response, dict):
            return
        metadata = response.get("ResponseMetadata")
        if isinstance(metadata, dict):
            self.aws_request_id = _request_id(metadata.get("RequestId"))
            self.aws_http_status = _bounded_int(
                metadata.get("HTTPStatusCode"), minimum=100, maximum=599
            )
            self.sdk_retry_attempts = _bounded_int(metadata.get("RetryAttempts"), maximum=100)
        if error:
            aws_error = response.get("Error")
            if isinstance(aws_error, dict) and aws_error.get("Code") in _AWS_ERROR_CODES:
                self.aws_error_code = aws_error["Code"]
            return
        stop_reason = response.get("stopReason")
        if isinstance(stop_reason, str) and stop_reason in _STOP_REASONS:
            self.stop_reason = stop_reason
        usage = response.get("usage")
        if isinstance(usage, dict):
            self.input_tokens = _bounded_int(usage.get("inputTokens"))
            self.output_tokens = _bounded_int(usage.get("outputTokens"))
            self.total_tokens = _bounded_int(usage.get("totalTokens"))
        metrics = response.get("metrics")
        if isinstance(metrics, dict):
            self.service_latency_ms = _bounded_int(metrics.get("latencyMs"))

    def wrap_converse(self, converse: Callable[..., Any]) -> Callable[..., Any]:
        def observed(*args: Any, **kwargs: Any) -> Any:
            try:
                response = converse(*args, **kwargs)
            except Exception as exc:
                self.exception_category = _exception_category(exc)
                if self.exception_category == "aws_service_error":
                    try:
                        self._capture(exc.response, error=True)
                    except Exception:
                        pass  # Diagnostics must not replace the provider exception.
                raise
            self.converse_returned = True
            try:
                self._capture(response, error=False)
            except Exception:
                pass  # Diagnostics must not alter the provider response.
            return response

        return observed

    def as_dict(self) -> dict[str, str | int | bool | None]:
        # Explicit projection: never serialize an SDK object or unknown field.
        return {
            "converse_returned": self.converse_returned,
            "exception_category": self.exception_category,
            "aws_error_code": self.aws_error_code,
            "aws_request_id": self.aws_request_id,
            "aws_http_status": self.aws_http_status,
            "sdk_retry_attempts": self.sdk_retry_attempts,
            "configured_region": self.configured_region,
            "configured_model": self.configured_model,
            "stop_reason": self.stop_reason,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "service_latency_ms": self.service_latency_ms,
            "local_parse_succeeded": self.local_parse_succeeded,
        }


def _install_live_observer(patch: pytest.MonkeyPatch, observation: _BedrockObservation) -> None:
    original_init = BedrockReportDraftGenerator.__init__
    original_generate = BedrockReportDraftGenerator.generate

    def observed_init(self: BedrockReportDraftGenerator, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self.client.converse = observation.wrap_converse(self.client.converse)

    def observed_generate(self: BedrockReportDraftGenerator, report: Any) -> Any:
        try:
            draft = original_generate(self, report)
        except Exception:
            if observation.converse_returned:
                observation.local_parse_succeeded = False
                observation.exception_category = "local_parse_error"
            raise
        if observation.converse_returned:
            observation.local_parse_succeeded = True
        return draft

    patch.setattr(BedrockReportDraftGenerator, "__init__", observed_init)
    patch.setattr(BedrockReportDraftGenerator, "generate", observed_generate)


@pytest.fixture(autouse=True)
def _isolate_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _load_live_values(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise RuntimeError("Missing .env.bedrock-live.local for opted-in Bedrock test")
    parsed = dotenv_values(path, interpolate=False)
    if set(parsed) - _LIVE_KEYS:
        raise RuntimeError("Bedrock live-test file contains unsupported setting names")
    values: dict[str, str] = {}
    for key in sorted(_LIVE_KEYS):
        value = parsed.get(key)
        if value is None or not value.strip():
            raise RuntimeError(f"Bedrock live-test file must set {key}")
        values[key] = value
    if values[_SECRET_KEY].strip().startswith("<") or values[_SECRET_KEY].strip() == "SET_LOCALLY":
        raise RuntimeError("Bedrock live-test bearer token must be set locally")
    if values["LLM_PROVIDER"].strip().lower() != "bedrock":
        raise RuntimeError("Bedrock live-test file must select LLM_PROVIDER=bedrock")
    return values


@contextmanager
def _scoped_live_configuration(path: Path) -> Iterator[None]:
    if os.environ.get("RUN_LIVE_BEDROCK_TESTS") != "1":
        pytest.skip("Opt-in Bedrock live test; local configuration was not opened")
    values = _load_live_values(path)
    with TemporaryDirectory(prefix="gnomon-bedrock-live-") as temporary_directory:
        empty_config = Path(temporary_directory) / "config"
        empty_credentials = Path(temporary_directory) / "credentials"
        empty_config.touch()
        empty_credentials.touch()
        scoped = pytest.MonkeyPatch()
        try:
            for key in _AWS_CREDENTIAL_ENV_KEYS:
                scoped.delenv(key, raising=False)
            scoped.setenv("AWS_CONFIG_FILE", str(empty_config))
            scoped.setenv("AWS_SHARED_CREDENTIALS_FILE", str(empty_credentials))
            scoped.setenv("BOTO_CONFIG", str(empty_config))
            scoped.setenv("AWS_EC2_METADATA_DISABLED", "true")
            for key, value in values.items():
                scoped.setenv(key, value)
            get_settings.cache_clear()
            yield
        finally:
            scoped.undo()
            get_settings.cache_clear()


def test_bedrock_live_configuration_reaches_provider_status_without_a_request() -> None:
    with _scoped_live_configuration(_LOCAL_FILE):
        settings = get_settings()
        status = provider_status(Request({"type": "http", "headers": []}))
        assert settings.llm_provider == "bedrock"
        assert status.credential_mode == "bearer_token"
        assert status.model_id == settings.model_id
        assert status.region == settings.aws_region
        assert status.max_output_tokens == settings.llm_max_output_tokens
        assert status.max_drafts_per_task == settings.llm_max_drafts_per_task


def test_bedrock_live_production_client_constructs_without_a_request() -> None:
    with _scoped_live_configuration(_LOCAL_FILE):
        settings = get_settings()
        observation = _BedrockObservation(settings.aws_region, settings.model_id)
        with pytest.MonkeyPatch.context() as patch:
            _install_live_observer(patch, observation)
            generator = BedrockReportDraftGenerator(
                model_id=settings.model_id,
                region=settings.aws_region,
                timeout_seconds=settings.llm_timeout_seconds,
                max_output_tokens=settings.llm_max_output_tokens,
            )
            assert callable(generator.client.converse)
        assert observation.converse_returned is False
        assert observation.local_parse_succeeded is None
        assert generator.model == "au.anthropic.claude-opus-4-6-v1"
        assert generator.client.meta.service_model.service_name == "bedrock-runtime"
        assert generator.client.meta.service_model.signing_name == "bedrock"


def test_one_live_bedrock_generation_through_gnomon() -> None:
    """One logical generation; keep synthetic durable evidence for inspection."""
    with _scoped_live_configuration(_LOCAL_FILE):
        settings = get_settings()
        assert settings.llm_provider == "bedrock"
        assert settings.aws_region == "ap-southeast-2"
        assert settings.model_id == "au.anthropic.claude-opus-4-6-v1"
        assert settings.llm_max_output_tokens == 1000
        assert settings.llm_max_drafts_per_task == 1
        assert settings.persistence_backend == "postgres"

        operation_id = uuid4()
        observation = _BedrockObservation(
            configured_region=settings.aws_region, configured_model=settings.model_id
        )
        with TestClient(create_app(), raise_server_exceptions=False) as client:
            assert "provider_session" not in client.cookies
            created = client.post(
                "/investigations",
                json={
                    "title": "Synthetic arithmetic baseline",
                    "objective": (
                        "Summarize the arithmetic fact that two plus two equals four. "
                        "No external evidence or private data is supplied."
                    ),
                    "questions": [{"question": "What is two plus two?", "priority": 3}],
                },
            )
            assert created.status_code == 201, "Synthetic investigation creation failed"
            task_id = UUID(created.json()["task"]["id"])

            started = monotonic()
            with pytest.MonkeyPatch.context() as patch:
                _install_live_observer(patch, observation)
                response = client.post(
                    f"/investigations/{task_id}/report/draft",
                    headers={"Idempotency-Key": str(operation_id)},
                )
            route_latency_ms = round((monotonic() - started) * 1000)

        with SessionFactory() as session:
            attempt = session.get(ReportGenerationAttemptRecord, operation_id)
            events = session.scalars(
                select(ResearchEventRecord)
                .where(
                    ResearchEventRecord.task_id == task_id,
                    ResearchEventRecord.payload["operation_id"].astext == str(operation_id),
                )
                .order_by(ResearchEventRecord.created_at, ResearchEventRecord.id)
            ).all()

        draft = response.json() if response.status_code == 200 else None
        audit = [
            {
                "event_type": event.event_type,
                "created_at": event.created_at.isoformat(),
                "provider": event.payload.get("provider"),
                "model": event.payload.get("model"),
                "input_tokens": event.payload.get("input_tokens"),
                "output_tokens": event.payload.get("output_tokens"),
                "total_tokens": event.payload.get("total_tokens"),
                "latency_ms": event.payload.get("latency_ms"),
                "reason": event.payload.get("reason"),
            }
            for event in events
        ]
        evidence = {
            "operation_id": str(operation_id),
            "task_id": str(task_id),
            "http_status": response.status_code,
            "route_latency_ms": route_latency_ms,
            "attempt_status": attempt.status if attempt else None,
            "attempt_error_reason": attempt.error_reason if attempt else None,
            "attempt_started_at": attempt.started_at.isoformat() if attempt else None,
            "attempt_finished_at": attempt.finished_at.isoformat()
            if attempt and attempt.finished_at
            else None,
            "audit": audit,
            "caller_provider": draft.get("provider") if draft else None,
            "caller_model": draft.get("model") if draft else None,
            "caller_usage": draft.get("usage") if draft else None,
            "caller_content_length": len(draft.get("content", "")) if draft else None,
            "provider_observation": observation.as_dict(),
            "draft_content_persisted": False,
        }
        print("BEDROCK_LIVE_BASELINE_EVIDENCE " + json.dumps(evidence, sort_keys=True))

        assert response.status_code == 200, "Gnomon did not return a draft"
        assert attempt is not None and attempt.status == "SUCCEEDED"
        assert [event.event_type for event in events] == [
            "report.draft_reserved",
            "report.draft_dispatched",
            "report.draft_generated",
        ]
        assert draft is not None and draft["provider"] == "aws_bedrock"
        assert draft["model"] == settings.model_id
        assert isinstance(draft["content"], str) and draft["content"]
        generated = events[-1].payload
        assert generated["provider"] == draft["provider"]
        assert generated["model"] == draft["model"]
        if draft.get("usage") is not None:
            for field in ("input_tokens", "output_tokens", "total_tokens"):
                assert generated[field] == draft["usage"][field]


def test_observer_preserves_one_converse_call_arguments_and_response() -> None:
    observation = _BedrockObservation("ap-southeast-2", "test-model")
    request_marker = object()
    options = {"body": {"prompt": "PROMPT_SENTINEL"}}
    request_id = str(uuid4())
    response = {
        "ResponseMetadata": {
            "RequestId": request_id,
            "HTTPStatusCode": 200,
            "RetryAttempts": 1,
            "HTTPHeaders": {"Authorization": "BEARER_SENTINEL"},
        },
        "stopReason": "end_turn",
        "usage": {"inputTokens": 2, "outputTokens": 3, "totalTokens": 5},
        "metrics": {"latencyMs": 42},
        "output": {"message": {"content": [{"text": "DRAFT_SENTINEL"}]}},
        "unknown": "UNKNOWN_SENTINEL",
    }
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def converse(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append((args, kwargs))
        return response

    result = observation.wrap_converse(converse)(request_marker, options=options)
    assert result is response
    assert len(calls) == 1
    assert calls[0][0][0] is request_marker
    assert calls[0][1]["options"] is options
    assert observation.as_dict() == {
        "converse_returned": True,
        "exception_category": None,
        "aws_error_code": None,
        "aws_request_id": request_id,
        "aws_http_status": 200,
        "sdk_retry_attempts": 1,
        "configured_region": "ap-southeast-2",
        "configured_model": "test-model",
        "stop_reason": "end_turn",
        "input_tokens": 2,
        "output_tokens": 3,
        "total_tokens": 5,
        "service_latency_ms": 42,
        "local_parse_succeeded": None,
    }
    serialized = json.dumps(observation.as_dict())
    for secret_or_content in (
        "PROMPT_SENTINEL",
        "DRAFT_SENTINEL",
        "BEARER_SENTINEL",
        "UNKNOWN_SENTINEL",
    ):
        assert secret_or_content not in serialized


def test_observer_preserves_service_exception_identity_and_allowlists_metadata() -> None:
    client_error = pytest.importorskip("botocore.exceptions").ClientError
    observation = _BedrockObservation("ap-southeast-2", "test-model")
    request_id = str(uuid4())
    failure = client_error(
        {
            "Error": {"Code": "ValidationException", "Message": "SECRET_MESSAGE_SENTINEL"},
            "ResponseMetadata": {
                "RequestId": request_id,
                "HTTPStatusCode": 400,
                "RetryAttempts": 2,
                "HTTPHeaders": {"Authorization": "BEARER_SENTINEL"},
            },
            "unknown": "UNKNOWN_SENTINEL",
        },
        "Converse",
    )
    calls = 0

    def converse() -> None:
        nonlocal calls
        calls += 1
        raise failure

    with pytest.raises(client_error) as caught:
        observation.wrap_converse(converse)()
    assert caught.value is failure
    assert calls == 1
    assert observation.converse_returned is False
    assert observation.local_parse_succeeded is None
    assert observation.exception_category == "aws_service_error"
    assert observation.aws_error_code == "ValidationException"
    assert observation.aws_request_id == request_id
    assert observation.aws_http_status == 400
    assert observation.sdk_retry_attempts == 2
    serialized = json.dumps(observation.as_dict())
    for secret_or_content in ("SECRET_MESSAGE_SENTINEL", "BEARER_SENTINEL", "UNKNOWN_SENTINEL"):
        assert secret_or_content not in serialized


def test_observer_rejects_unknown_service_fields() -> None:
    client_error = pytest.importorskip("botocore.exceptions").ClientError
    observation = _BedrockObservation("ap-southeast-2", "test-model")
    failure = client_error(
        {
            "Error": {"Code": "SECRET_CODE_SENTINEL", "Message": "SECRET_MESSAGE_SENTINEL"},
            "ResponseMetadata": {
                "RequestId": "SECRET_REQUEST_SENTINEL",
                "HTTPStatusCode": "SECRET_STATUS_SENTINEL",
                "RetryAttempts": "SECRET_RETRY_SENTINEL",
            },
        },
        "Converse",
    )

    def converse() -> None:
        raise failure

    with pytest.raises(client_error):
        observation.wrap_converse(converse)()
    assert observation.exception_category == "aws_service_error"
    assert observation.aws_error_code is None
    assert observation.aws_request_id is None
    assert observation.aws_http_status is None
    assert observation.sdk_retry_attempts is None
    assert "SECRET" not in json.dumps(observation.as_dict())


@pytest.mark.parametrize(
    ("failure_kind", "category"),
    [
        ("read_timeout", "timeout"),
        ("parameter_error", "local_parameter_error"),
        ("runtime_error", "other"),
    ],
)
def test_observer_preserves_response_free_exception(failure_kind: str, category: str) -> None:
    if failure_kind == "read_timeout":
        failure = pytest.importorskip("botocore.exceptions").ReadTimeoutError(
            endpoint_url="https://example.invalid"
        )
    elif failure_kind == "parameter_error":
        failure = pytest.importorskip("botocore.exceptions").ParamValidationError(
            report="PROMPT_SENTINEL"
        )
    else:
        failure = RuntimeError("SECRET_MESSAGE_SENTINEL")
    observation = _BedrockObservation("ap-southeast-2", "test-model")

    def converse() -> None:
        raise failure

    with pytest.raises(type(failure)) as caught:
        observation.wrap_converse(converse)()
    assert caught.value is failure
    assert observation.exception_category == category
    assert observation.converse_returned is False
    assert observation.aws_request_id is None
    assert observation.aws_http_status is None
    assert observation.sdk_retry_attempts is None
    assert "SENTINEL" not in json.dumps(observation.as_dict())


@pytest.mark.parametrize("valid_draft", [False, True])
def test_observer_distinguishes_local_parse_after_converse(
    valid_draft: bool,
) -> None:
    pytest.importorskip("botocore.exceptions")
    observation = _BedrockObservation("ap-southeast-2", "test-model")
    text = (
        '{"content":"DRAFT_SENTINEL","cited_source_ids":[],"cited_claim_ids":[],"limitations":[]}'
        if valid_draft
        else "DRAFT_SENTINEL not JSON"
    )
    response = {
        "ResponseMetadata": {"RequestId": str(uuid4()), "HTTPStatusCode": 200},
        "output": {"message": {"content": [{"text": text}]}},
    }
    calls = 0

    def converse(**_kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return response

    def fake_init(self: BedrockReportDraftGenerator, model_id: str, region: str) -> None:
        self.model = model_id
        self.max_output_tokens = 1000
        self.client = SimpleNamespace(converse=converse)

    report = SimpleNamespace(
        task_id=uuid4(), model_dump=lambda **_kwargs: {"input": "PROMPT_SENTINEL"}
    )
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(BedrockReportDraftGenerator, "__init__", fake_init)
        _install_live_observer(patch, observation)
        generator = BedrockReportDraftGenerator("test-model", "ap-southeast-2")
        if valid_draft:
            assert generator.generate(report).content == "DRAFT_SENTINEL"
            assert observation.local_parse_succeeded is True
            assert observation.exception_category is None
        else:
            with pytest.raises(ValueError):
                generator.generate(report)
            assert observation.local_parse_succeeded is False
            assert observation.exception_category == "local_parse_error"
    assert calls == 1
    assert observation.converse_returned is True
    assert observation.aws_http_status == 200
    assert "SENTINEL" not in json.dumps(observation.as_dict())


def _write_test_config(path: Path, *, token_line: str | None = None, extra: str = "") -> None:
    lines = [
        "LLM_PROVIDER=bedrock",
        "AWS_REGION=ap-southeast-2",
        "MODEL_ID=test-model",
        "LLM_MAX_OUTPUT_TOKENS=1000",
        "LLM_MAX_DRAFTS_PER_TASK=1",
    ]
    if token_line is not None:
        lines.append(token_line)
    if extra:
        lines.append(extra)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_no_opt_in_skips_before_opening_local_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("RUN_LIVE_BEDROCK_TESTS", raising=False)
    with pytest.raises(pytest.skip.Exception, match="Opt-in Bedrock live test"):
        with _scoped_live_configuration(tmp_path / "does-not-exist"):
            pytest.fail("The live configuration must not be entered")


def test_opt_in_requires_local_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("RUN_LIVE_BEDROCK_TESTS", "1")
    with pytest.raises(RuntimeError, match="Missing .env.bedrock-live.local"):
        with _scoped_live_configuration(tmp_path / "does-not-exist"):
            pytest.fail("A missing file must not be accepted")


@pytest.mark.parametrize(
    "token_line",
    [None, "AWS_BEARER_TOKEN_BEDROCK=", "AWS_BEARER_TOKEN_BEDROCK=<SET_LOCALLY>"],
)
def test_missing_empty_or_placeholder_token_fails_without_echoing_value(
    monkeypatch, tmp_path: Path, token_line: str | None
) -> None:
    monkeypatch.setenv("RUN_LIVE_BEDROCK_TESTS", "1")
    path = tmp_path / "config"
    _write_test_config(path, token_line=token_line)
    with pytest.raises(RuntimeError) as failure:
        with _scoped_live_configuration(path):
            pytest.fail("An unset token must not be accepted")
    assert _SECRET_KEY in str(failure.value) or "bearer token" in str(failure.value)
    assert "<SET_LOCALLY>" not in str(failure.value)


def test_live_file_overrides_ambient_values_then_restores_them(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("RUN_LIVE_BEDROCK_TESTS", "1")
    ambient = {
        "LLM_PROVIDER": "stub",
        "AWS_REGION": "desktop-region",
        "MODEL_ID": "desktop-model",
        "LLM_MAX_OUTPUT_TOKENS": "77",
        "LLM_MAX_DRAFTS_PER_TASK": "3",
        _SECRET_KEY: "DESKTOP_TEST_ONLY",
    }
    for key, value in ambient.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    before = get_settings()
    path = tmp_path / "config"
    _write_test_config(path, token_line=f"{_SECRET_KEY}=UNIT_TEST_ONLY")

    with _scoped_live_configuration(path):
        configured = get_settings()
        assert configured.llm_provider == "bedrock"
        assert configured.aws_region == "ap-southeast-2"
        assert configured.model_id == "test-model"
        assert configured.llm_max_output_tokens == 1000
        assert configured.llm_max_drafts_per_task == 1
        assert os.environ[_SECRET_KEY] == "UNIT_TEST_ONLY"
        assert (
            provider_status(Request({"type": "http", "headers": []})).credential_mode
            == "bearer_token"
        )

    assert get_settings() is not configured
    assert get_settings() is not before
    assert get_settings().llm_provider == "stub"
    assert get_settings().model_id == "desktop-model"
    assert all(os.environ[key] == value for key, value in ambient.items())
    get_settings.cache_clear()


def test_aws_credential_sources_are_isolated_and_restored(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("RUN_LIVE_BEDROCK_TESTS", "1")
    ambient = {
        **{key: "preexisting-test-value" for key in _AWS_CREDENTIAL_ENV_KEYS},
        "AWS_CONFIG_FILE": "preexisting-config-path",
        "AWS_SHARED_CREDENTIALS_FILE": "preexisting-credentials-path",
        "BOTO_CONFIG": "preexisting-boto-path",
        "AWS_EC2_METADATA_DISABLED": "false",
        _SECRET_KEY: "PREEXISTING_TEST_TOKEN",
    }
    for key, value in ambient.items():
        monkeypatch.setenv(key, value)
    path = tmp_path / "config"
    _write_test_config(path, token_line=f"{_SECRET_KEY}=UNIT_TEST_ONLY")

    with _scoped_live_configuration(path):
        assert all(key not in os.environ for key in _AWS_CREDENTIAL_ENV_KEYS)
        assert os.environ[_SECRET_KEY] == "UNIT_TEST_ONLY"
        assert os.environ["AWS_EC2_METADATA_DISABLED"] == "true"
        empty_config = Path(os.environ["AWS_CONFIG_FILE"])
        empty_credentials = Path(os.environ["AWS_SHARED_CREDENTIALS_FILE"])
        assert empty_config.is_file() and empty_config.read_bytes() == b""
        assert empty_credentials.is_file() and empty_credentials.read_bytes() == b""
        assert os.environ["BOTO_CONFIG"] == str(empty_config)

    assert all(os.environ[key] == value for key, value in ambient.items())
    assert not empty_config.exists()
    assert not empty_credentials.exists()


def test_live_configuration_restores_environment_after_test_failure(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("RUN_LIVE_BEDROCK_TESTS", "1")
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.delenv(_SECRET_KEY, raising=False)
    path = tmp_path / "config"
    _write_test_config(path, token_line=f"{_SECRET_KEY}=UNIT_TEST_ONLY")
    with pytest.raises(RuntimeError, match="synthetic test failure"):
        with _scoped_live_configuration(path):
            assert get_settings().llm_provider == "bedrock"
            temporary_config = Path(os.environ["AWS_CONFIG_FILE"])
            raise RuntimeError("synthetic test failure")
    assert os.environ["LLM_PROVIDER"] == "stub"
    assert _SECRET_KEY not in os.environ
    assert not temporary_config.exists()
    assert get_settings().llm_provider == "stub"
    get_settings.cache_clear()


def test_live_configuration_rejects_non_allowlisted_keys(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("RUN_LIVE_BEDROCK_TESTS", "1")
    path = tmp_path / "config"
    _write_test_config(
        path,
        token_line=f"{_SECRET_KEY}=UNIT_TEST_ONLY",
        extra="LLM_API_KEY=UNIT_TEST_ONLY",
    )
    with pytest.raises(RuntimeError, match="unsupported setting names"):
        with _scoped_live_configuration(path):
            pytest.fail("Extra settings must not be loaded")
