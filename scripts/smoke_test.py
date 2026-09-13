"""Run the local end-to-end prototype smoke test against PostgreSQL."""

from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import delete

from research_agent.api.app import create_app
from research_agent.persistence.database import engine
from research_agent.persistence.models import ResearchTaskRecord


def main() -> None:
    with TestClient(create_app()) as client:
        health = client.get("/health")
        assert health.status_code == 200, health.text
        task_response = client.post(
            "/investigations",
            json={
                "title": "Prototype smoke test",
                "objective": "Verify the local research loop.",
                "questions": [{"question": "What should be verified?"}],
            },
        )
        assert task_response.status_code == 201, task_response.text
        task_id = UUID(task_response.json()["task"]["id"])
        try:
            run = client.post(
                f"/investigations/{task_id}/cycles/1/run",
                json={"scenario": "honest", "max_agents": 2},
            )
            assert run.status_code == 200, run.text
            cycle = run.json()["task"]["cycles"][0]
            assert cycle["status"] == "completed"
            assert len(cycle["evidence_ids"]) == 2
            assert cycle["claim_ids"]
            report = client.get(f"/investigations/{task_id}/report")
            assert report.status_code == 200, report.text
            assert report.json()["agent_comparison"]["independent_agent_count"] == 2
        finally:
            with engine.begin() as connection:
                connection.execute(
                    delete(ResearchTaskRecord).where(ResearchTaskRecord.id == task_id)
                )
    print("Prototype smoke test passed")


if __name__ == "__main__":
    main()
