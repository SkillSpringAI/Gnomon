from fastapi.testclient import TestClient

from research_agent.api.app import create_app
from research_agent.application.research_service import InMemoryResearchTaskRepository


def test_create_and_continue_open_ended_investigation() -> None:
    client = TestClient(create_app(InMemoryResearchTaskRepository()))
    brief = {
        "title": "Societal adaptation to technology",
        "objective": "Test whether evidence supports fears about rapid technological change.",
        "hypotheses": [
            {
                "label": "H1",
                "statement": "Institutional adaptation lags behind technology adoption.",
            }
        ],
        "questions": [
            {
                "question": "Which fears have strong empirical support?",
                "priority": 1,
            }
        ],
        "case_studies": [],
        "methods": ["web_research", "case_study", "agent_questioning"],
        "evidence_requirements": ["Prefer systematic reviews and official statistics."],
        "stopping_criteria": ["Compare at least three contrasting cases."],
    }

    created = client.post("/investigations", json=brief)

    assert created.status_code == 201
    task = created.json()["task"]
    assert task["status"] == "active"
    assert len(task["cycles"]) == 1
    assert task["cycles"][0]["number"] == 1

    continued = client.post(f"/investigations/{task['id']}/cycles")

    assert continued.status_code == 200
    assert len(continued.json()["task"]["cycles"]) == 2
    assert continued.json()["task"]["cycles"][1]["number"] == 2


def test_unknown_investigation_returns_not_found() -> None:
    client = TestClient(create_app(InMemoryResearchTaskRepository()))

    response = client.get("/investigations/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404


def test_cycle_can_start_and_record_a_bounded_outcome() -> None:
    client = TestClient(create_app(InMemoryResearchTaskRepository()))
    created = client.post(
        "/investigations",
        json={"title": "Cycle", "objective": "Track a bounded result."},
    )
    task = created.json()["task"]

    started = client.post(f"/investigations/{task['id']}/cycles/1/start")
    assert started.status_code == 200
    assert started.json()["task"]["cycles"][0]["status"] == "active"

    outcome = client.post(
        f"/investigations/{task['id']}/cycles/1/outcome",
        json={
            "status": "completed",
            "result_summary": "The evidence boundary is now explicit.",
            "unresolved_objectives": [],
        },
    )
    assert outcome.status_code == 200
    cycle = outcome.json()["task"]["cycles"][0]
    assert cycle["status"] == "completed"
    assert cycle["result_summary"] == "The evidence boundary is now explicit."
    assert cycle["completed_at"] is not None


def test_cycle_outcome_requires_active_cycle() -> None:
    client = TestClient(create_app(InMemoryResearchTaskRepository()))
    task = client.post(
        "/investigations", json={"title": "Cycle", "objective": "Track state."}
    ).json()["task"]
    response = client.post(
        f"/investigations/{task['id']}/cycles/1/outcome",
        json={"status": "failed", "result_summary": "It did not start."},
    )
    assert response.status_code == 409


def test_rejected_cycle_does_not_mutate_in_memory_task() -> None:
    import pytest

    from research_agent.application.research_service import ResearchService, TaskStateConflict
    from research_agent.domain.research import ResearchBrief, TaskStatus, TaskStatusChange

    repository = InMemoryResearchTaskRepository()
    service = ResearchService(repository)
    task = service.create_task(ResearchBrief(title="Lifecycle", objective="Guard inactive tasks."))
    for task_status in [
        TaskStatus.PLANNED,
        TaskStatus.PAUSED,
        TaskStatus.BLOCKED,
        TaskStatus.CONCLUDED,
        TaskStatus.ABANDONED,
    ]:
        task.status = task_status
        repository.save(task)
        before = repository.get(task.id)
        with pytest.raises(TaskStateConflict):
            service.plan_next_cycle(task.id)
        assert repository.get(task.id) == before
    with pytest.raises(TaskStateConflict):
        service.change_status(
            task.id,
            TaskStatusChange(
                status=TaskStatus.ACTIVE,
                expected_status=TaskStatus.ABANDONED,
            ),
        )
    assert repository.get(task.id).status == TaskStatus.ABANDONED
