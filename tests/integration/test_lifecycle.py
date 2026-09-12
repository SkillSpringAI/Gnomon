"""Persisted lifecycle, cycle history, and concurrent-operation contracts."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, select

from research_agent.api.app import create_app
from research_agent.persistence.database import engine
from research_agent.persistence.models import (
    ResearchCycleRecord,
    ResearchEventRecord,
    ResearchTaskRecord,
)


@pytest.fixture
def lifecycle_task():
    with TestClient(create_app()) as client:
        response = client.post(
            "/investigations", json={"title": "Lifecycle", "objective": "Test durable control."}
        )
        assert response.status_code == 201
        task_id = response.json()["task"]["id"]
        try:
            yield client, task_id
        finally:
            with engine.begin() as connection:
                connection.execute(
                    delete(ResearchTaskRecord).where(ResearchTaskRecord.id == UUID(task_id))
                )


def change(client, task_id, before, after):
    return client.patch(
        f"/investigations/{task_id}/status",
        json={
            "expected_status": before,
            "status": after,
        },
    )


def cycle_rows(task_id):
    with engine.connect() as connection:
        return connection.execute(
            select(ResearchCycleRecord.id, ResearchCycleRecord.cycle_number)
            .where(ResearchCycleRecord.task_id == UUID(task_id))
            .order_by(ResearchCycleRecord.cycle_number)
        ).all()


def test_status_survives_restart_and_preserves_cycle_ids(lifecycle_task):
    client, task_id = lifecycle_task
    original_rows = cycle_rows(task_id)
    paused = change(client, task_id, "active", "paused")
    assert paused.status_code == 200, paused.text
    assert change(client, task_id, "active", "paused").json() == paused.json()
    assert client.post(f"/investigations/{task_id}/cycles").status_code == 409
    assert change(client, task_id, "active", "blocked").status_code == 409
    with TestClient(create_app()) as fresh:
        assert fresh.get(f"/investigations/{task_id}").json()["task"]["status"] == "paused"
        assert change(fresh, task_id, "paused", "blocked").status_code == 200
        assert fresh.post(f"/investigations/{task_id}/cycles").status_code == 409
        assert change(fresh, task_id, "blocked", "active").status_code == 200
        continued = fresh.post(f"/investigations/{task_id}/cycles")
        assert continued.status_code == 200, continued.text
        assert [cycle["number"] for cycle in continued.json()["task"]["cycles"]] == [1, 2]
        assert change(fresh, task_id, "active", "concluded").status_code == 200
        assert fresh.post(f"/investigations/{task_id}/cycles").status_code == 409
        assert change(fresh, task_id, "concluded", "active").status_code == 409
        assert cycle_rows(task_id)[0] == original_rows[0]
        events = fresh.get(f"/investigations/{task_id}/events").json()
        assert [item["event_type"] for item in events] == [
            "task.created",
            "task.status_changed",
            "task.status_changed",
            "task.status_changed",
            "cycle.planned",
            "task.status_changed",
        ]
        assert events[1]["payload"]["from_status"] == "active"
        assert events[1]["payload"]["to_status"] == "paused"
        assert events[4]["payload"]["cycle_number"] == 2
        assert (
            fresh.get(f"/investigations/{task_id}/snapshot").json()["task"]["status"] == "concluded"
        )


def test_concurrent_cycles_have_distinct_numbers(lifecycle_task):
    _, task_id = lifecycle_task
    barrier = Barrier(2)

    def plan():
        with TestClient(create_app()) as client:
            barrier.wait(timeout=5)
            result = client.post(f"/investigations/{task_id}/cycles")
            assert result.status_code == 200, result.text
            return result.json()

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: plan(), range(2)))
    assert sorted(len(result["task"]["cycles"]) for result in results) == [2, 3]
    assert [row.cycle_number for row in cycle_rows(task_id)] == [1, 2, 3]


def test_pause_and_cycle_are_serialized(lifecycle_task):
    _, task_id = lifecycle_task
    barrier = Barrier(2)

    def run(operation):
        with TestClient(create_app()) as client:
            barrier.wait(timeout=5)
            if operation == "pause":
                return change(client, task_id, "active", "paused")
            return client.post(f"/investigations/{task_id}/cycles")

    with ThreadPoolExecutor(max_workers=2) as workers:
        paused, cycle = list(workers.map(run, ["pause", "cycle"]))
    assert paused.status_code == 200
    assert cycle.status_code in {200, 409}
    with TestClient(create_app()) as client:
        current = client.get(f"/investigations/{task_id}").json()["task"]
        assert current["status"] == "paused"
        assert len(current["cycles"]) == (2 if cycle.status_code == 200 else 1)
        assert client.post(f"/investigations/{task_id}/cycles").status_code == 409


@pytest.mark.parametrize("operation", ["status", "cycle"])
def test_audit_failure_rolls_back_lifecycle_write(lifecycle_task, operation):
    client, task_id = lifecycle_task
    original = client.get(f"/investigations/{task_id}").json()
    original_rows = cycle_rows(task_id)

    def reject(*args):
        raise RuntimeError("Audit unavailable")

    event.listen(ResearchEventRecord, "before_insert", reject)
    try:
        with pytest.raises(RuntimeError, match="Audit unavailable"):
            if operation == "status":
                change(client, task_id, "active", "paused")
            else:
                client.post(f"/investigations/{task_id}/cycles")
    finally:
        event.remove(ResearchEventRecord, "before_insert", reject)
    assert client.get(f"/investigations/{task_id}").json() == original
    assert cycle_rows(task_id) == original_rows
    assert [
        row["event_type"] for row in client.get(f"/investigations/{task_id}/events").json()
    ] == ["task.created"]


def test_status_request_validation(lifecycle_task):
    client, task_id = lifecycle_task
    assert change(client, str(uuid4()), "active", "paused").status_code == 404
    assert (
        client.patch(f"/investigations/{task_id}/status", json={"status": "paused"}).status_code
        == 422
    )
    assert change(client, task_id, "active", "invalid").status_code == 422
    assert change(client, task_id, "active", "planned").status_code == 409
    assert change(client, task_id, "active", "abandoned").status_code == 200
    assert change(client, task_id, "abandoned", "active").status_code == 409
    assert client.post(f"/investigations/{task_id}/cycles").status_code == 409
