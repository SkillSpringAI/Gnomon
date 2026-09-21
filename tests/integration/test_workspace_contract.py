"""Contract coverage for the operator workspace's state-driven controls."""

from uuid import UUID

import pytest
from conftest import purge_test_tasks
from fastapi.testclient import TestClient

from research_agent.api.app import create_app
from research_agent.persistence.database import engine


@pytest.fixture
def workspace_task():
    with TestClient(create_app()) as client:
        response = client.post(
            "/investigations",
            json={
                "title": "Workspace contract",
                "objective": "Verify operator state transitions.",
            },
        )
        assert response.status_code == 201
        task = response.json()["task"]
        task_id = UUID(task["id"])
        try:
            yield client, task
        finally:
            with engine.begin() as connection:
                purge_test_tasks(connection, [task_id])


def report(client, task_id):
    response = client.get(f"/investigations/{task_id}/report")
    assert response.status_code == 200, response.text
    return response.json()


def test_workspace_contains_state_driven_controls_and_no_credentials(workspace_task):
    client, task = workspace_task
    response = client.get(f"/investigations/{task['id']}/workspace")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    for control in (
        "Refresh report", "Run local agent cycle", "Plan next cycle",
        "Pause investigation", "Generate draft", "Cycle history",
        "Unresolved objectives", "Agent comparisons", "Retained progress",
        "Attempt status", "explicit operator action",
        "Attempted objectives",
        "Stopping decision", "evidence basis changed; review required",
    ):
        assert control in response.text
    assert "__TASK_ID__" not in response.text
    assert "AWS_BEARER_TOKEN_BEDROCK" not in response.text
    assert "provider_session" not in response.text
    assert "textContent" in response.text


def test_initial_report_exposes_planned_cycle_and_active_controls(workspace_task):
    client, task = workspace_task
    current = report(client, task["id"])
    assert current["task_status"] == "active"
    assert [cycle["status"] for cycle in current["cycles"]] == ["planned"]
    assert current["cycles"][0]["result_summary"] is None
    assert current["unresolved_objectives"] == []


def test_paused_report_cannot_plan_or_run(workspace_task):
    client, task = workspace_task
    task_id = task["id"]
    paused = client.patch(
        f"/investigations/{task_id}/status",
        json={"expected_status": "active", "status": "paused"},
    )
    assert paused.status_code == 200
    assert report(client, task_id)["task_status"] == "paused"
    assert client.post(f"/investigations/{task_id}/cycles").status_code == 409
    assert client.post(f"/investigations/{task_id}/cycles/1/run", json={}).status_code == 409


def test_completed_cycle_exposes_outcome_and_enables_next_plan(workspace_task):
    client, task = workspace_task
    task_id = task["id"]
    run = client.post(f"/investigations/{task_id}/cycles/1/run", json={"max_agents": 1})
    assert run.status_code == 200, run.text
    current = report(client, task_id)
    cycle = current["cycles"][0]
    assert cycle["status"] == "completed"
    assert cycle["result_summary"]
    assert cycle["evidence_ids"] and cycle["claim_ids"]
    assert cycle["unresolved_objectives"] == cycle["objectives"]
    assert current["unresolved_objectives"] == cycle["objectives"]
    next_cycle = client.post(f"/investigations/{task_id}/cycles")
    assert next_cycle.status_code == 200, next_cycle.text
    assert report(client, task_id)["cycles"][-1]["status"] == "planned"


def test_active_cycle_report_disables_plan_and_duplicate_run(workspace_task):
    client, task = workspace_task
    task_id = task["id"]
    started = client.post(f"/investigations/{task_id}/cycles/1/start")
    assert started.status_code == 200
    current = report(client, task_id)
    assert current["cycles"][0]["status"] == "active"
    assert client.post(f"/investigations/{task_id}/cycles").status_code == 409
    assert client.post(f"/investigations/{task_id}/cycles/1/run", json={}).status_code == 409
    outcome = client.post(
        f"/investigations/{task_id}/cycles/1/outcome",
        json={
            "status": "blocked",
            "result_summary": "Operator stopped the active cycle.",
            "unresolved_objectives": current["cycles"][0]["objectives"],
        },
    )
    assert outcome.status_code == 200
    refreshed = report(client, task_id)
    assert refreshed["cycles"][0]["status"] == "blocked"
    assert refreshed["cycles"][0]["result_summary"] == "Operator stopped the active cycle."


def test_run_request_records_selected_objectives(workspace_task):
    client, task = workspace_task
    task_id = task["id"]
    first = client.post(f"/investigations/{task_id}/cycles/1/run", json={"max_agents": 1})
    assert first.status_code == 200
    planned = client.post(f"/investigations/{task_id}/cycles")
    assert planned.status_code == 200
    cycle = planned.json()["task"]["cycles"][-1]
    assert len(cycle["objectives"]) >= 2
    run = client.post(
        f"/investigations/{task_id}/cycles/{cycle['number']}/run",
        json={"max_agents": 1, "objective_indices": [0, 1]},
    )
    assert run.status_code == 200, run.text
    result = run.json()["task"]["cycles"][-1]
    assert result["attempted_objectives"] == result["objectives"][:2]
    assert result["unresolved_objectives"] == result["objectives"]


@pytest.mark.parametrize("indices", [[], [0, 0], [99]])
def test_run_request_rejects_invalid_objective_selection(workspace_task, indices):
    client, task = workspace_task
    response = client.post(
        f"/investigations/{task['id']}/cycles/1/run",
        json={"objective_indices": indices},
    )
    assert response.status_code == 422
    assert report(client, task["id"])["cycles"][0]["status"] == "planned"


def test_stale_lifecycle_write_returns_conflict_and_state_remains_authoritative(workspace_task):
    client, task = workspace_task
    task_id = task["id"]
    first = client.patch(
        f"/investigations/{task_id}/status",
        json={"expected_status": "active", "status": "paused"},
    )
    assert first.status_code == 200
    stale = client.patch(
        f"/investigations/{task_id}/status",
        json={"expected_status": "active", "status": "concluded"},
    )
    assert stale.status_code == 409
    assert report(client, task_id)["task_status"] == "paused"


def test_outcome_objectives_must_belong_to_the_cycle(workspace_task):
    client, task = workspace_task
    task_id = task["id"]
    assert client.post(f"/investigations/{task_id}/cycles/1/start").status_code == 200
    invalid = client.post(
        f"/investigations/{task_id}/cycles/1/outcome",
        json={
            "status": "completed",
            "result_summary": "Invalid metadata test.",
            "attempted_objectives": ["Unplanned work."],
        },
    )
    assert invalid.status_code == 409
    assert report(client, task_id)["cycles"][0]["status"] == "active"
