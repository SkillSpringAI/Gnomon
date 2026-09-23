"""Caller caveats cannot displace derived stopping-decision warnings."""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from test_stopping_decisions import _cleanup, _new_task, _request

from research_agent.api.app import create_app


@pytest.mark.parametrize("overlap", [False, True])
@pytest.mark.parametrize("unresolved", [False, True])
def test_maximum_caller_limitations_preserve_system_warnings_and_replay(overlap, unresolved):
    with TestClient(create_app()) as client:
        created = client.post(
            "/investigations",
            json={
                "title": "Limitation preservation",
                "objective": "Retain uncertainty",
                "hypotheses": [{"label": "H1", "statement": "Unassessed proposition"}],
            },
        )
        assert created.status_code == 201
        task = UUID(created.json()["task"]["id"])
        try:
            source = client.post(
                f"/investigations/{task}/sources",
                json={"source_type": "document", "title": "Evidence", "content": "Observation"},
            )
            assert source.status_code == 201, source.text
            if unresolved:
                source_id = source.json()["id"]
                claim = client.post(
                    f"/investigations/{task}/claims",
                    json={
                        "statement": "Inconclusive observation",
                        "source_links": [{"source_id": source_id, "support_type": "supporting"}],
                    },
                )
                assert claim.status_code == 201, claim.text
                hypothesis_id = created.json()["task"]["brief"]["hypotheses"][0]["id"]
                assessment = client.put(
                    f"/investigations/{task}/hypotheses/{hypothesis_id}/assessment",
                    json={
                        "status": "unresolved",
                        "summary": "Insufficient evidence",
                        "evidence_links": [
                            {"claim_id": claim.json()["id"], "relation": "supporting"}
                        ],
                    },
                )
                assert assessment.status_code == 200, assessment.text
            ready = client.get(f"/investigations/{task}/stopping-decision/readiness").json()
            if unresolved:
                assert any(
                    item["code"] == "unresolved_assessment" and item["status"] == "attention"
                    for item in ready["items"]
                )
            warnings = [item["detail"] for item in ready["items"] if item["status"] != "satisfied"]
            assert len(warnings) >= 2
            caller = [f"Operator caveat {index}" for index in range(20)]
            if overlap:
                caller[0] = warnings[0]
            body = _request(ready, limitations=caller)
            first = client.post(f"/investigations/{task}/stopping-decision", json=body)
            assert first.status_code == 201, first.text
            decision = first.json()
            expected = list(dict.fromkeys(warnings + caller))
            assert decision["limitations"] == expected
            assert len(expected) <= 20 + len(ready["items"])

            retry = client.post(f"/investigations/{task}/stopping-decision", json=body)
            assert retry.status_code == 201, retry.text
            assert retry.json() == decision
            current = client.get(f"/investigations/{task}/stopping-decision")
            assert current.json() == decision
            history = client.get(f"/investigations/{task}/stopping-decision/history").json()
            assert len(history) == 1
            assert history[0]["resulting_state"]["limitations"] == expected
            report = client.get(f"/investigations/{task}/report")
            assert report.status_code == 200, report.text
            assert report.json()["stopping_decision"]["limitations"] == expected
            events = client.get(f"/investigations/{task}/events").json()
            assert sum(e["event_type"] == "task.stopping_decision_recorded" for e in events) == 1
        finally:
            _cleanup(task)


def test_caller_limit_still_rejects_twenty_one_entries():
    with TestClient(create_app()) as client:
        task, ready = _new_task(client)
        try:
            response = client.post(
                f"/investigations/{task}/stopping-decision",
                json=_request(ready, limitations=[f"Caveat {i}" for i in range(21)]),
            )
            assert response.status_code == 422
            assert client.get(f"/investigations/{task}/stopping-decision/history").json() == []
            assert client.get(f"/investigations/{task}").json()["task"]["status"] == "active"
        finally:
            _cleanup(task)


@pytest.mark.parametrize("supplied", [False, True])
def test_readiness_marks_no_evidence_and_resource_limits_as_operator_reported(supplied):
    with TestClient(create_app()) as client:
        task, readiness = _new_task(client)
        try:
            items = {item["code"]: item for item in readiness["items"]}
            assert items["no_evidence"]["status"] == "attention"
            request = _request(
                readiness,
                reason="resource_limited",
                runtime_limit_evidence=["Operator reported deadline reached"] if supplied else [],
            )
            accepted = client.post(
                f"/investigations/{task}/stopping-decision",
                json=request,
            )
            assert accepted.status_code == 201, accepted.text
            assert accepted.json()["limitations"][-1] == (
                "Runtime limits are operator-reported and are not system-verified."
                if supplied
                else "Resource limitation was reported without runtime evidence."
            )
        finally:
            _cleanup(task)
