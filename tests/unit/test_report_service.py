import pytest

from research_agent.adapters.llm.bedrock_bearer_report import BedrockBearerReportDraftGenerator
from research_agent.adapters.llm.bedrock_report import BedrockReportDraftGenerator, _usage
from research_agent.adapters.llm.rule_based_report import RuleBasedReportDraftGenerator
from research_agent.application.report_generation_service import (
    ReportGenerationError,
    ReportGenerationService,
)
from research_agent.application.report_service import ReportService
from research_agent.application.research_service import (
    InMemoryResearchTaskRepository,
    ResearchService,
)
from research_agent.domain.research import ResearchBrief


def test_report_preserves_uncertainty_and_omits_source_content() -> None:
    repository = InMemoryResearchTaskRepository()
    task = ResearchService(repository).create_task(
        ResearchBrief(
            title="Report test",
            objective="Build an evidence inventory.",
            questions=[{"question": "What remains uncertain?", "priority": 1}],
        )
    )
    report = ReportService().build(repository.planning_snapshot(task.id))

    assert report.task_id == task.id
    assert report.hypotheses == []
    assert report.claims == []
    assert report.sources == []
    assert report.open_questions == ["What remains uncertain?"]
    assert "No source evidence" in report.limitations[0]
    assert not hasattr(report, "source_content")


def test_rule_based_draft_declares_limits_and_provider() -> None:
    repository = InMemoryResearchTaskRepository()
    task = ResearchService(repository).create_task(
        ResearchBrief(title="Draft test", objective="Keep uncertainty visible.")
    )
    report = ReportService().build(repository.planning_snapshot(task.id))
    draft = RuleBasedReportDraftGenerator().generate(report)

    assert draft.provider == "rule_based"
    assert draft.model == "local-development"
    assert "does not establish conclusions" in draft.content
    assert draft.task_id == task.id


def test_rule_based_draft_includes_claim_and_cycle_inventory() -> None:
    repository = InMemoryResearchTaskRepository()
    task = ResearchService(repository).create_task(
        ResearchBrief(title="Rich draft", objective="Preserve provenance.")
    )
    report = ReportService().build(repository.planning_snapshot(task.id))
    draft = RuleBasedReportDraftGenerator().generate(report)

    assert "Evidence inventory" in draft.content
    assert "does not establish conclusions" in draft.content


def test_bedrock_usage_is_redacted_and_defaults_total_tokens() -> None:
    usage = _usage({"usage": {"inputTokens": 12, "outputTokens": 8}})
    assert usage is not None
    assert usage.model_dump() == {
        "input_tokens": 12,
        "output_tokens": 8,
        "total_tokens": 20,
    }
    assert _usage({"usage": {"inputTokens": -1, "outputTokens": 8}}) is None


def test_report_generation_rejects_provider_citations_outside_report() -> None:
    class InvalidGenerator:
        def generate(self, report):
            return {
                "task_id": report.task_id,
                "provider": "test",
                "model": "invalid",
                "generated_at": "2026-01-01T00:00:00Z",
                "content": "draft",
                "cited_source_ids": ["00000000-0000-0000-0000-000000000001"],
            }

    repository = InMemoryResearchTaskRepository()
    task = ResearchService(repository).create_task(
        ResearchBrief(title="Invalid", objective="Reject invalid output.")
    )
    report = ReportService().build(repository.planning_snapshot(task.id))
    try:
        ReportGenerationService(InvalidGenerator()).generate(report)
    except ReportGenerationError:
        pass
    else:
        raise AssertionError("invalid provider citations must be rejected")


@pytest.mark.parametrize("adapter_kind", ["bedrock", "bearer"])
def test_bedrock_adapters_produce_the_same_validated_contract(
    monkeypatch: pytest.MonkeyPatch, adapter_kind: str
) -> None:
    repository = InMemoryResearchTaskRepository()
    task = ResearchService(repository).create_task(
        ResearchBrief(title="Provider parity", objective="Preserve one contract.")
    )
    report = ReportService().build(repository.planning_snapshot(task.id))
    payload = {
        "output": {
            "message": {
                "content": [
                    {
                        "text": '{"content":"draft","cited_source_ids":[],'
                        '"cited_claim_ids":[],"limitations":[]}'
                    }
                ]
            }
        },
        "usage": {"inputTokens": 2, "outputTokens": 3, "totalTokens": 5},
    }
    if adapter_kind == "bedrock":
        adapter = BedrockReportDraftGenerator.__new__(BedrockReportDraftGenerator)
        adapter.model = "test-model"
        adapter.max_output_tokens = 3000

        class Client:
            def converse(self, **_: object) -> dict[str, object]:
                return payload

        adapter.client = Client()
    else:
        adapter = BedrockBearerReportDraftGenerator.__new__(BedrockBearerReportDraftGenerator)
        adapter.token = "test-token"
        adapter.model = "test-model"
        adapter.url = "https://example.test/converse"
        adapter.timeout = None

        class Response:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return payload

        monkeypatch.setattr(
            "research_agent.adapters.llm.bedrock_bearer_report.httpx.post",
            lambda *args, **kwargs: Response(),
        )
    draft = ReportGenerationService(adapter).generate(report)
    assert draft.provider in {"aws_bedrock", "aws_bedrock_session"}
    assert draft.task_id == report.task_id
    assert draft.usage is not None and draft.usage.total_tokens == 5
