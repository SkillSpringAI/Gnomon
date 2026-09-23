"""Bounded discovery of current declarations, including retracted history heads."""

from itertools import combinations
from uuid import uuid4

from fastapi.testclient import TestClient

pytest_plugins = ["test_source_dependence_contract"]

from research_agent.api.app import create_app  # noqa: E402
from research_agent.application import source_dependence_service  # noqa: E402
from research_agent.application.security_capability import SecurityCapabilityDenied  # noqa: E402


def test_relationship_pages_are_bounded_task_scoped_and_include_retractions(dependence_context):
    task_id, sources = dependence_context
    base = f"/investigations/{task_id}"
    with TestClient(create_app()) as client:
        for index in range(11):
            response = client.post(
                base + "/sources",
                json={
                    "source_type": "document",
                    "title": f"Page source {index}",
                    "content": str(index),
                },
            )
            assert response.status_code == 201
            sources.append(response.json()["id"])
        created = []
        for a, b in list(combinations(sources, 2))[:101]:
            response = client.post(
                base + "/source-dependence/relationships",
                json={
                    "kind": "common_origin",
                    "source_a_id": str(a),
                    "source_b_id": str(b),
                    "reason": "Pagination fixture",
                },
            )
            assert response.status_code == 201, response.text
            created.append(response.json())
        path = base + "/source-dependence/relationships"
        retracted_id = created[0]["relationship_id"]
        response = client.patch(
            path + "/" + retracted_id,
            json={
                "relationship_id": retracted_id,
                "expected_revision": 1,
                "operation": "RETRACT",
                "reason": "Keep history discoverable",
            },
        )
        assert response.status_code == 200, response.text
        first = client.get(path).json()
        assert len(first["items"]) == 100
        assert first["next_after"] == first["items"][-1]["relationship_id"]
        second = client.get(path, params={"after": first["next_after"]}).json()
        assert len(second["items"]) == 1
        assert second["next_after"] is None
        items = first["items"] + second["items"]
        ids = [item["relationship_id"] for item in items]
        assert ids == sorted(item["relationship_id"] for item in created)
        assert (
            next(item for item in items if item["relationship_id"] == retracted_id)["lifecycle"]
            == "retracted"
        )
        assert all(item["task_id"] == str(task_id) for item in items)
        assert client.get(path, params={"after": ids[-1]}).json() == {
            "items": [],
            "next_after": None,
        }
        assert client.get(path, params={"after": "not-a-uuid"}).status_code == 422
        assert (
            client.get(f"/investigations/{uuid4()}/source-dependence/relationships").status_code
            == 404
        )


def test_relationship_listing_requires_read_authority(dependence_context, monkeypatch):
    task_id, _ = dependence_context

    def deny(*args, **kwargs):
        raise SecurityCapabilityDenied("Read authority denied")

    monkeypatch.setattr(source_dependence_service, "require_capability", deny)
    with TestClient(create_app()) as client:
        assert (
            client.get(f"/investigations/{task_id}/source-dependence/relationships").status_code
            == 403
        )
