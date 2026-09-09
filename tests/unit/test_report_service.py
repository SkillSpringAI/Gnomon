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
