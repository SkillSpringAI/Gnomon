"""Browser regression tests: RUN_BROWSER_TESTS=1; install Chromium first."""

import os
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
import pytest
from test_source_cycle import source_cycle  # noqa: F401

from research_agent.application.source_dependence_service import SourceDependenceService
from research_agent.domain.research import SourceDependenceLimits

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_BROWSER_TESTS") != "1", reason="Opt-in browser regression suite"
)


@pytest.fixture
def workspace_browser(request):
    fixture = request.getfixturevalue("source_cycle")
    try:
        from playwright import sync_api as playwright
    except ImportError:
        if os.environ.get("RUN_BROWSER_TESTS") == "1":
            raise
        pytest.skip("Playwright is not installed")
    client, task_id, url, calls, settings = fixture
    with playwright.sync_playwright() as runtime:
        channel = os.environ.get("PLAYWRIGHT_CHANNEL", "msedge" if os.name == "nt" else "chromium")
        executable_path = os.environ.get("PLAYWRIGHT_EXECUTABLE_PATH")
        launch_options = {"headless": True}
        if executable_path:
            launch_options["executable_path"] = executable_path
        else:
            launch_options["channel"] = channel
        browser = runtime.chromium.launch(**launch_options)
        page = browser.new_page(viewport={"width": 1100, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def bridge(route):
            request = route.request
            target = urlsplit(request.url)
            response = client.request(
                request.method,
                target.path + (f"?{target.query}" if target.query else ""),
                content=request.post_data_buffer,
                headers={"content-type": request.headers.get("content-type", "application/json")},
            )
            route.fulfill(
                status=response.status_code,
                body=response.content,
                headers={"content-type": response.headers.get("content-type", "text/plain")},
            )

        page.route("http://workspace.test/**", bridge)
        page.goto(f"http://workspace.test/investigations/{task_id}/workspace")
        playwright.expect(page.locator("#message")).to_have_text("Report loaded.")
        try:
            yield page, playwright.expect, fixture
            assert errors == []
        finally:
            browser.close()


@pytest.mark.parametrize("partial", [False, True])
def test_source_controls_and_partial_result_reload(workspace_browser, partial):
    page, expect, (client, task_id, url, calls, settings) = workspace_browser
    if partial:
        page.set_viewport_size({"width": 390, "height": 844})
    expect(page.locator("#run-sources")).to_be_disabled()
    page.locator("#source-url-0").fill("ftp://example.org/file")
    expect(page.locator("#source-validation")).to_contain_text("HTTP or HTTPS")
    page.locator("#source-url-0").fill(url + "/a")
    expect(page.locator("#run-sources")).to_be_disabled()
    page.locator("#source-objective-0").select_option("1")
    page.locator("#source-url-1").fill(url + "/b")
    page.locator("#source-objective-1").select_option("0")
    expect(page.locator("#run-sources")).to_be_enabled()
    settings["handler"] = lambda request: httpx.Response(
        200 if not partial or len(calls) == 1 else 503,
        headers={"content-type": "text/plain"},
        text="A retained source supports investigation.",
    )
    pending = []
    page.route("**/run-sources", lambda route: pending.append(route))
    page.locator("#run-sources").click()
    expect(page.locator("#source-url-0")).to_be_disabled()
    expect(page.locator("#run-cycle")).to_be_disabled()
    assert len(pending) == 1
    request = pending[0].request.post_data_json
    assert request == {
        "sources": [
            {"uri": url + "/a", "objective_index": 1},
            {"uri": url + "/b", "objective_index": 0},
        ]
    }
    response = client.post(f"/investigations/{task_id}/cycles/1/run-sources", json=request)
    pending[0].fulfill(status=response.status_code, json=response.json())
    expect(page.locator("#message")).to_contain_text("blocked" if partial else "completed")
    page.reload()
    expect(page.locator("#message")).to_have_text("Report loaded.")
    page.get_by_text("Evidence by objective", exact=True).click()
    expect(page.locator("#cycles")).to_contain_text("2. Check premise B.")
    expect(page.locator("#cycles")).to_contain_text("A retained source supports investigation.")
    expect(page.locator("#cycles")).to_contain_text("Retained progress")
    expect(page.locator("#cycles")).to_contain_text(
        f"Attempt status: {'BLOCKED' if partial else 'COMPLETED'}"
    )
    expect(page.locator("#cycles")).to_contain_text(f"Retained evidence ({1 if partial else 2})")
    expect(page.locator("#cycles")).to_contain_text("Evidence")
    if partial:
        expect(page.locator("#cycles")).to_contain_text("Attempted; no source was retained.")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    expect(page.locator("#plan-cycle")).to_be_enabled()
    if screenshot := os.environ.get("WORKSPACE_SCREENSHOT"):
        page.screenshot(path=screenshot, full_page=True)
    page.locator("#plan-cycle").click()
    expect(page.locator("#source-url-0")).to_be_enabled()
    expect(page.locator("#source-url-0")).to_have_value("")


def test_objective_selection_and_stale_state(workspace_browser):
    page, expect, (client, task_id, url, _, _) = workspace_browser
    page.locator('#objective-choices input[value="0"]').uncheck()
    expect(page.locator("#run-cycle")).to_be_disabled()
    page.locator('#objective-choices input[value="1"]').check()
    page.locator("#source-url-0").fill(url)
    page.locator("#source-objective-0").select_option("1")
    assert (
        client.patch(
            f"/investigations/{task_id}/status",
            json={"expected_status": "active", "status": "paused"},
        ).status_code
        == 200
    )
    page.locator("#run-cycle").click()
    expect(page.locator("#message")).to_contain_text("investigation changed")
    expect(page.locator("#source-url-0")).to_be_disabled()
    expect(page.locator("#source-url-0")).to_have_value(url)
    page.locator("#lifecycle").click()
    expect(page.locator("#source-url-0")).to_be_enabled()
    expect(page.locator('#objective-choices input[value="1"]')).to_be_checked()
    page.locator("#run-cycle").click()
    expect(page.locator("#message")).to_contain_text("completed")
    cycle = client.get(f"/investigations/{task_id}").json()["task"]["cycles"][0]
    assert cycle["attempted_objectives"] == ["Check premise B."]
    assert [item["objective_index"] for item in cycle["objective_results"]] == [1]
    page.route("**/report", lambda route: route.fulfill(status=503, body="Unavailable"))
    page.locator("#refresh").click()
    expect(page.locator("#message")).to_contain_text("displayed history may be stale")
    expect(page.locator("#source-url-0")).to_be_disabled()


def test_review_history_correction_and_stale_evidence(workspace_browser):
    page, expect, (client, task_id, _, _, _) = workspace_browser
    page.locator("#run-cycle").click()
    expect(page.locator("#message")).to_contain_text("completed")
    expect(page.locator("#review-panel")).to_be_visible()
    page.locator("#review-decision").select_option("completed")
    page.locator("#review-rationale").fill("Reviewed the evidence; collection remains unverified.")
    expect(page.locator("#save-review")).to_be_disabled()
    page.get_by_text("Select evidence references", exact=True).click()
    page.locator("#review-claims input").first.check()
    page.locator("#save-review").click()
    expect(page.locator("#message")).to_contain_text("Objective review saved")
    state = client.get(f"/investigations/{task_id}/report").json()
    assert "Review premise A." not in state["unresolved_objectives"]
    page.reload()
    expect(page.locator("#message")).to_have_text("Report loaded.")
    page.locator("#review-rationale").fill("Further checking is needed.")
    page.locator("#save-review").click()
    expect(page.locator("#message")).to_contain_text("Objective review saved")
    state = client.get(f"/investigations/{task_id}/report").json()
    assert [item["decision"] for item in state["cycles"][0]["objective_reviews"]] == [
        "completed",
        "unresolved",
    ]
    page.locator("#review-rationale").fill("This submission will become stale.")
    assert (
        client.post(
            f"/investigations/{task_id}/sources",
            json={
                "source_type": "document",
                "title": "New evidence",
                "content": "Evidence changed.",
            },
        ).status_code
        == 201
    )
    page.locator("#save-review").click()
    expect(page.locator("#message")).to_contain_text("investigation changed")
    state = client.get(f"/investigations/{task_id}/report").json()
    assert len(state["cycles"][0]["objective_reviews"]) == 2
    page.get_by_text("Objective review history", exact=True).click()
    expect(page.locator("#cycles")).to_contain_text("Further checking is needed.")
    expect(page.locator("#cycles")).to_contain_text("evidence changed")
    if screenshot := os.environ.get("WORKSPACE_SCREENSHOT"):
        page.screenshot(path=screenshot, full_page=True)
    page.locator("#plan-cycle").click()
    expect(page.locator("#message")).to_contain_text("planned")
    expect(page.locator("#review-panel")).to_be_hidden()


def test_operator_recovery_from_workspace(workspace_browser):
    page, expect, (client, task_id, _, _, _) = workspace_browser
    assert client.post(f"/investigations/{task_id}/cycles/1/start").status_code == 200
    page.locator("#refresh").click()
    expect(page.locator("#recovery-panel")).to_be_visible()
    expect(page.locator("#recovery-tracking")).to_contain_text("no durable runner tracking")
    expect(page.locator("#recover-cycle")).to_be_disabled()
    page.locator("#recovery-reason").fill("The previous worker was interrupted.")
    assert (
        client.patch(
            f"/investigations/{task_id}/status",
            json={"expected_status": "active", "status": "paused"},
        ).status_code
        == 200
    )
    page.locator("#recover-cycle").click()
    expect(page.locator("#message")).to_contain_text("investigation changed")
    page.locator("#recovery-reason").fill("Close the interrupted cycle and retain its evidence.")
    page.locator("#recover-cycle").click()
    expect(page.locator("#message")).to_contain_text("Cycle closed")
    expect(page.locator("#recovery-panel")).to_be_hidden()
    expect(page.locator("#status")).to_contain_text("paused")
    page.reload()
    expect(page.locator("#message")).to_have_text("Report loaded.")
    expect(page.locator("#cycles")).to_contain_text("Operator recovery")
    page.locator("#lifecycle").click()
    expect(page.locator("#plan-cycle")).to_be_enabled()
    page.locator("#plan-cycle").click()
    expect(page.locator("#message")).to_contain_text("planned")


def test_source_dependence_editor_supports_directional_and_symmetric_edges(workspace_browser):
    page, expect, (client, task_id, url, _, _) = workspace_browser
    sources = []
    for suffix in ("/source-a", "/source-b", "/source-c"):
        response = client.post(
            f"/investigations/{task_id}/sources",
            json={"source_type": "document", "title": f"Source {suffix[-1]}", "content": suffix},
        )
        assert response.status_code == 201, response.text
        sources.append(response.json()["id"])
    page.locator("#refresh").click()
    expect(page.locator("#dependence-editor")).to_be_visible()
    page.locator("#dependence-derived").select_option(sources[1])
    page.locator("#dependence-upstream").select_option(sources[0])
    page.locator("#dependence-reason").fill("B was derived from A.")
    page.locator("#create-dependence").click()
    expect(page.locator("#message")).to_contain_text("relationship declared")
    expect(page.locator("#dependence-rows")).to_contain_text("derived_from")
    expect(page.locator("#dependence-rows")).to_contain_text(
        f"Source b ({sources[1][:8]}) → Source a ({sources[0][:8]})"
    )
    page.get_by_text("Bounded dependence graph", exact=True).click()
    expect(page.locator("#dependence-boundary")).to_contain_text("do not establish independence")
    expect(page.locator("#dependence-edges")).to_contain_text("Source")
    current_direction = client.get(f"/investigations/{task_id}/report").json()["source_dependence"][
        "examined_relationships"
    ][0]["direction"]
    corrected_direction = "high_to_low" if current_direction == "low_to_high" else "low_to_high"
    page.on(
        "dialog",
        lambda dialog: dialog.accept(
            corrected_direction if "Direction" in dialog.message else "Correct the declaration."
        ),
    )
    page.get_by_role("button", name="Correct direction").click()
    expect(page.locator("#message")).to_contain_text("relationship corrected")
    page.get_by_role("button", name="Reverse latest change").click()
    expect(page.locator("#message")).to_contain_text("reversal recorded")
    expect(page.locator("#dependence-rows")).to_contain_text(
        f"Source b ({sources[1][:8]}) → Source a ({sources[0][:8]})"
    )
    page.get_by_role("button", name="Show history").first.click()
    expect(page.locator("#dependence-rows")).to_contain_text("Relationship history")
    page.locator("#dependence-kind").select_option("common_origin")
    page.locator("#dependence-source-a").select_option(sources[0])
    page.locator("#dependence-source-b").select_option(sources[2])
    page.locator("#dependence-reason").fill("A and C share an origin.")
    page.locator("#create-dependence").click()
    expect(page.locator("#message")).to_contain_text("relationship declared")
    expect(page.locator("#dependence-rows")).to_contain_text("common_origin")
    page.locator("#dependence-rows article").last.get_by_role("button", name="Retract").click()
    expect(page.locator("#message")).to_contain_text("relationship updated")


def test_stopping_editor_submits_current_readiness_basis(workspace_browser):
    page, expect, (client, task_id, _, _, _) = workspace_browser
    source = client.post(
        f"/investigations/{task_id}/sources",
        json={"source_type": "document", "title": "Stopping evidence", "content": "Reviewed."},
    )
    assert source.status_code == 201
    page.locator("#refresh").click()
    expect(page.locator("#stopping-editor")).to_be_visible()
    expect(page.locator("#stopping-readiness")).to_contain_text("attention")
    page.get_by_text("Select evidence and planning references", exact=True).click()
    page.locator("#stopping-sources input").first.check()
    page.locator("#stopping-objectives input").first.check()
    page.locator("#stopping-rationale").fill("The operator reviewed the bounded evidence.")
    page.locator("#stopping-limitations").fill("Operator review remains advisory.")
    page.locator("#submit-stopping").click()
    expect(page.locator("#message")).to_contain_text("Stopping decision recorded")
    expect(page.locator("#stopping-decision")).to_contain_text("Reason: evidence_sufficient")
    expect(page.locator("#submit-stopping")).to_be_disabled()
    history = client.get(f"/investigations/{task_id}/stopping-decision/history")
    assert history.status_code == 200
    assert len(history.json()) == 1
    events = client.get(f"/investigations/{task_id}/events").json()
    assert sum(item["event_type"] == "task.stopping_decision_recorded" for item in events) == 1
    accepted = history.json()[0]["resulting_state"]
    assert accepted["source_ids"] == [source.json()["id"]]
    assert accepted["objective_cycle_number"] == 1
    assert accepted["objective_indices"] == [0]
    page.reload()
    expect(page.locator("#message")).to_have_text("Report loaded.")
    expect(page.locator("#submit-stopping")).to_be_disabled()
    assert (
        client.get(f"/investigations/{task_id}/stopping-decision/history").json() == history.json()
    )


def test_source_dependence_editor_surfaces_stale_revision_and_reload(workspace_browser):
    page, expect, (client, task_id, _, _, _) = workspace_browser
    sources = []
    for suffix in ("/stale-a", "/stale-b"):
        response = client.post(
            f"/investigations/{task_id}/sources",
            json={"source_type": "document", "title": suffix, "content": suffix},
        )
        assert response.status_code == 201
        sources.append(response.json()["id"])
    created = client.post(
        f"/investigations/{task_id}/source-dependence/relationships",
        json={
            "derived_source_id": sources[1],
            "upstream_source_id": sources[0],
            "kind": "derived_from",
            "reason": "Initial declaration",
        },
    )
    assert created.status_code == 201, created.text
    relationship = created.json()
    page.locator("#refresh").click()
    expect(page.locator("#dependence-rows")).to_contain_text("derived_from")
    expect(page.locator("#message")).to_contain_text("Report refreshed")
    changed = client.patch(
        f"/investigations/{task_id}/source-dependence/relationships/{relationship['relationship_id']}",
        json={
            "relationship_id": relationship["relationship_id"],
            "expected_revision": 1,
            "operation": "SET",
            "direction": "high_to_low"
            if relationship["direction"] == "low_to_high"
            else "low_to_high",
            "lifecycle": "active",
            "reason": "Concurrent correction",
        },
    )
    assert changed.status_code == 200, changed.text
    expect(page.locator("#dependence-rows")).to_contain_text("derived_from")
    page.on(
        "dialog",
        lambda dialog: dialog.accept(
            "low_to_high" if "Direction" in dialog.message else "Stale UI correction"
        ),
    )
    page.get_by_role("button", name="Correct direction").click()
    expect(page.locator("#message")).to_contain_text("investigation changed")
    page.reload()
    expect(page.locator("#message")).to_have_text("Report loaded.")
    page.get_by_role("button", name="Show history").first.click()
    expect(page.locator("#dependence-rows")).to_contain_text("Concurrent correction")


def test_stopping_resource_limit_reference_survives_reload_and_history(workspace_browser):
    page, expect, (client, task_id, _, _, _) = workspace_browser
    source = client.post(
        f"/investigations/{task_id}/sources",
        json={"source_type": "document", "title": "Budget evidence", "content": "Reviewed."},
    )
    assert source.status_code == 201
    page.locator("#refresh").click()
    page.get_by_text("Select evidence and planning references", exact=True).click()
    page.locator("#stopping-sources input").first.check()
    page.locator("#stopping-rationale").fill("The available execution budget was reached.")
    page.locator("#stopping-reason").select_option("resource_limited")
    page.locator("#stopping-runtime").fill("Operator reported deadline reached.")
    page.locator("#submit-stopping").click()
    expect(page.locator("#message")).to_contain_text("Stopping decision recorded")
    expect(page.locator("#stopping-decision")).to_contain_text("resource_limited")
    expect(page.locator("#stopping-decision")).to_contain_text("operator-reported")
    page.reload()
    expect(page.locator("#message")).to_have_text("Report loaded.")
    history = client.get(f"/investigations/{task_id}/stopping-decision/history")
    assert history.status_code == 200
    assert history.json()[0]["resulting_state"]["runtime_limit_evidence"] == [
        "Operator reported deadline reached."
    ]


def test_stopping_editor_surfaces_stale_readiness_basis(workspace_browser):
    page, expect, (client, task_id, _, _, _) = workspace_browser
    page.locator("#stopping-rationale").fill("Submit against the displayed basis.")
    changed = client.post(
        f"/investigations/{task_id}/sources",
        json={"source_type": "document", "title": "Concurrent evidence", "content": "Changed."},
    )
    assert changed.status_code == 201
    page.locator("#submit-stopping").click()
    expect(page.locator("#message")).to_contain_text("investigation changed")
    expect(page.locator("#stopping-decision")).to_contain_text("No stopping decision")
    expect(page.locator("#submit-stopping")).to_be_enabled()
    assert client.get(f"/investigations/{task_id}/stopping-decision/history").json() == []
    assert client.get(f"/investigations/{task_id}").json()["task"]["status"] == "active"
    page.locator("#submit-stopping").click()
    expect(page.locator("#message")).to_contain_text("Stopping decision recorded")
    assert len(client.get(f"/investigations/{task_id}/stopping-decision/history").json()) == 1


def test_stopping_disabled_when_readiness_refresh_fails(workspace_browser):
    page, expect, _ = workspace_browser
    page.locator("#stopping-rationale").fill("Review current evidence.")
    expect(page.locator("#submit-stopping")).to_be_enabled()
    page.route("**/stopping-decision/readiness", lambda route: route.fulfill(status=503))
    page.locator("#refresh").click()
    expect(page.locator("#message")).to_contain_text("displayed history may be stale")
    expect(page.locator("#submit-stopping")).to_be_disabled()


def test_stopping_denial_preserves_state_and_allows_authorized_retry(
    workspace_browser, monkeypatch
):
    from research_agent.application import stopping_decision_service
    from research_agent.application.security_capability import SecurityCapabilityDenied

    page, expect, (client, task_id, _, _, _) = workspace_browser
    original = stopping_decision_service.require_locked_capability

    def deny(*args, **kwargs):
        raise SecurityCapabilityDenied("denied")

    monkeypatch.setattr(stopping_decision_service, "require_locked_capability", deny)
    page.locator("#stopping-rationale").fill("Reviewed before submission.")
    page.locator("#submit-stopping").click()
    expect(page.locator("#message")).to_contain_text("not permitted")
    assert client.get(f"/investigations/{task_id}/stopping-decision/history").json() == []
    assert client.get(f"/investigations/{task_id}").json()["task"]["status"] == "active"
    monkeypatch.setattr(stopping_decision_service, "require_locked_capability", original)
    page.locator("#submit-stopping").click()
    expect(page.locator("#message")).to_contain_text("Stopping decision recorded")
    assert len(client.get(f"/investigations/{task_id}/stopping-decision/history").json()) == 1


def test_bounded_graph_view_preserves_truncation_and_unknown_language(
    workspace_browser, monkeypatch
):
    page, expect, (client, task_id, _, _, _) = workspace_browser
    source_ids = []
    for suffix in ("/bound-a", "/bound-b"):
        response = client.post(
            f"/investigations/{task_id}/sources",
            json={"source_type": "document", "title": suffix, "content": suffix},
        )
        assert response.status_code == 201
        source_ids.append(response.json()["id"])
    relationship = client.post(
        f"/investigations/{task_id}/source-dependence/relationships",
        json={
            "derived_source_id": source_ids[1],
            "upstream_source_id": source_ids[0],
            "kind": "derived_from",
            "reason": "Bounded graph fixture",
        },
    )
    assert relationship.status_code == 201
    monkeypatch.setattr(
        SourceDependenceService,
        "LIMITS",
        SourceDependenceLimits(max_visited_sources=1, max_hops=8),
    )
    page.locator("#refresh").click()
    page.get_by_text("Bounded dependence graph", exact=True).click()
    expect(page.locator("#dependence-boundary")).to_contain_text("truncated")
    expect(page.locator("#dependence-boundary")).to_contain_text("unknown")


def test_invalid_graph_view_preserves_warning_language(workspace_browser, monkeypatch):
    page, expect, (client, task_id, _, _, _) = workspace_browser
    source_ids = []
    for suffix in ("/invalid-a", "/invalid-b"):
        response = client.post(
            f"/investigations/{task_id}/sources",
            json={"source_type": "document", "title": suffix, "content": suffix},
        )
        assert response.status_code == 201
        source_ids.append(response.json()["id"])
    relationship = client.post(
        f"/investigations/{task_id}/source-dependence/relationships",
        json={
            "derived_source_id": source_ids[1],
            "upstream_source_id": source_ids[0],
            "kind": "derived_from",
            "reason": "Invalid graph fixture",
        },
    )
    assert relationship.status_code == 201
    monkeypatch.setattr(SourceDependenceService, "_has_directed_cycle", lambda *args: True)
    page.locator("#refresh").click()
    page.get_by_text("Bounded dependence graph", exact=True).click()
    expect(page.locator("#dependence-boundary")).to_contain_text("Invalid directed graph")
    expect(page.locator("#dependence-boundary")).to_contain_text("must not be used")


@pytest.mark.parametrize("kind", ["stopping", "relationship"])
@pytest.mark.parametrize("committed", [False, True])
def test_uncertain_write_retries_exact_command_after_reload(workspace_browser, kind, committed):
    page, expect, (client, task_id, _, _, _) = workspace_browser
    base = f"/investigations/{task_id}"
    if kind == "relationship":
        ids = []
        for title in ("Original", "Derived"):
            result = client.post(
                base + "/sources",
                json={
                    "source_type": "document",
                    "title": title,
                    "content": title,
                },
            )
            assert result.status_code == 201
            ids.append(result.json()["id"])
        page.locator("#refresh").click()
        expect(page.locator("#dependence-derived option")).to_have_count(3)
        page.locator("#dependence-derived").select_option(ids[1])
        page.locator("#dependence-upstream").select_option(ids[0])
        page.locator("#dependence-reason").fill("Recorded once.")
        path = "/source-dependence/relationships"
        button = "#create-dependence"
    else:
        path = "/stopping-decision"
        button = "#submit-stopping"
        page.locator("#stopping-rationale").fill("Recorded once.")
    requests = []

    def uncertain(route):
        if route.request.method == "GET":
            route.fallback()
            return
        payload = route.request.post_data_json
        requests.append(payload)
        if len(requests) == 1:
            if committed:
                result = client.post(base + path, json=payload)
                assert result.status_code in (200, 201), result.text
            route.abort("failed")
        else:
            result = client.post(base + path, json=payload)
            route.fulfill(status=result.status_code, json=result.json())

    page.route("**" + path, uncertain)
    page.locator(button).click()
    expect(page.locator("#pending-command")).to_be_visible()
    expect(page.locator(button)).to_be_disabled()
    page.reload()
    expect(page.locator("#message")).to_have_text("Report loaded.")
    expect(page.locator("#pending-command")).to_be_visible()
    page.locator("#retry-command").click()
    expect(page.locator("#message")).to_contain_text("Original request confirmed")
    expect(page.locator("#pending-command")).to_be_hidden()
    assert len(requests) == 2
    assert requests[0] == requests[1]
    assert requests[0]["operation_id"]
    if kind == "relationship":
        items = client.get(base + path).json()["items"]
        assert len(items) == 1
        history = client.get(base + path + f"/{items[0]['relationship_id']}/history").json()
    else:
        history = client.get(base + path + "/history").json()
        events = client.get(base + "/events").json()
        assert sum(e["event_type"] == "task.stopping_decision_recorded" for e in events) == 1
    assert len(history) == 1


def test_retracted_relationship_survives_reload_and_can_be_reversed(workspace_browser):
    page, expect, (client, task_id, _, _, _) = workspace_browser
    base = f"/investigations/{task_id}"
    ids = [
        client.post(
            base + "/sources",
            json={
                "source_type": "document",
                "title": title,
                "content": title,
            },
        ).json()["id"]
        for title in ("A", "B")
    ]
    created = client.post(
        base + "/source-dependence/relationships",
        json={
            "kind": "derived_from",
            "derived_source_id": ids[1],
            "upstream_source_id": ids[0],
            "reason": "Initial declaration",
        },
    )
    assert created.status_code == 201
    relationship_id = created.json()["relationship_id"]
    page.reload()
    expect(page.locator("#message")).to_have_text("Report loaded.")
    page.on("dialog", lambda dialog: dialog.accept("Operator correction."))
    page.get_by_role("button", name="Retract", exact=True).click()
    expect(page.locator("#message")).to_contain_text("relationship updated")
    page.reload()
    expect(page.locator("#message")).to_have_text("Report loaded.")
    expect(page.locator("#dependence-rows")).to_contain_text("retracted")
    page.get_by_role("button", name="Show history").click()
    expect(page.locator("#dependence-rows")).to_contain_text("Operator correction.")
    page.get_by_role("button", name="Reverse latest change").click()
    expect(page.locator("#message")).to_contain_text("reversal recorded")
    history = client.get(
        base + f"/source-dependence/relationships/{relationship_id}/history"
    ).json()
    assert len(history) == 3
    assert (
        client.get(base + f"/source-dependence/relationships/{relationship_id}").json()["lifecycle"]
        == "active"
    )


def test_expired_reversal_explains_failure_without_changes(workspace_browser, monkeypatch):
    from research_agent.application import source_dependence_service

    page, expect, (client, task_id, _, _, _) = workspace_browser
    base = f"/investigations/{task_id}"
    ids = [
        client.post(
            base + "/sources",
            json={
                "source_type": "document",
                "title": title,
                "content": title,
            },
        ).json()["id"]
        for title in ("A", "B")
    ]
    created = client.post(
        base + "/source-dependence/relationships",
        json={
            "kind": "derived_from",
            "derived_source_id": ids[1],
            "upstream_source_id": ids[0],
            "reason": "Initial declaration",
        },
    )
    assert created.status_code == 201
    path = base + f"/source-dependence/relationships/{created.json()['relationship_id']}"
    before = client.get(path + "/history").json()

    class FutureClock:
        @staticmethod
        def now(tz):
            return datetime.now(UTC) + timedelta(hours=49)

    monkeypatch.setattr(source_dependence_service, "datetime", FutureClock)
    page.reload()
    expect(page.locator("#message")).to_have_text("Report loaded.")
    page.on("dialog", lambda dialog: dialog.accept("Reverse old declaration."))
    page.get_by_role("button", name="Reverse latest change").click()
    expect(page.locator("#message")).to_contain_text("reversal window has expired")
    assert client.get(path + "/history").json() == before
    assert client.get(path).json() == created.json()


def test_stopping_selects_earlier_cycle_claim_review_and_rejects_invalid_reference(
    workspace_browser,
):
    page, expect, (client, task_id, _, _, _) = workspace_browser
    page.locator("#run-cycle").click()
    expect(page.locator("#message")).to_contain_text("completed")
    page.locator("#review-decision").select_option("completed")
    page.locator("#review-rationale").fill("Evidence reviewed.")
    page.get_by_text("Select evidence references", exact=True).click()
    page.locator("#review-claims input").first.check()
    page.locator("#save-review").click()
    expect(page.locator("#message")).to_contain_text("Objective review saved")
    page.locator("#plan-cycle").click()
    expect(page.locator("#message")).to_contain_text("planned")
    page.get_by_text("Select evidence and planning references", exact=True).click()
    expect(page.locator("#stopping-cycle option")).to_have_count(2)
    page.locator("#stopping-cycle").select_option("1")
    page.locator("#stopping-objectives input").first.check()
    page.locator("#stopping-claims input").first.check()
    page.locator("#stopping-reviews input").first.check()
    claim_id = page.locator("#stopping-claims input").first.input_value()
    review_id = page.locator("#stopping-reviews input").first.input_value()
    page.locator("#stopping-rationale").fill("Reviewed earlier cycle evidence.")
    path = f"/investigations/{task_id}/stopping-decision"

    def invalid(route):
        payload = route.request.post_data_json
        payload["claim_ids"] = [str(uuid4())]
        result = client.post(path, json=payload)
        assert result.status_code == 409
        route.fulfill(status=result.status_code, json=result.json())

    page.route("**/stopping-decision", invalid)
    page.locator("#submit-stopping").click()
    expect(page.locator("#message")).to_contain_text("reference is no longer valid")
    assert client.get(path + "/history").json() == []
    page.unroute("**/stopping-decision", invalid)
    page.locator("#submit-stopping").click()
    expect(page.locator("#message")).to_contain_text("Stopping decision recorded")
    accepted = client.get(path + "/history").json()[0]["resulting_state"]
    assert accepted["objective_cycle_number"] == 1
    assert accepted["objective_indices"] == [0]
    assert accepted["claim_ids"] == [claim_id]
    assert accepted["review_ids"] == [review_id]


@pytest.mark.parametrize(
    "limit,reason",
    [
        ({"max_examined_relationships": 1}, "edge_limit"),
        ({"max_hops": 0, "max_frontier_sources": 1}, "depth_limit"),
        ({"max_visited_sources": 1, "max_frontier_sources": 0}, "node_limit"),
    ],
)
def test_graph_overflow_and_frontier_display_from_real_projection(
    workspace_browser, monkeypatch, limit, reason
):
    page, expect, (client, task_id, _, _, _) = workspace_browser
    base = f"/investigations/{task_id}"
    ids = [
        client.post(
            base + "/sources",
            json={
                "source_type": "document",
                "title": title,
                "content": title,
            },
        ).json()["id"]
        for title in ("Root", "Branch A", "Branch B")
    ]
    for derived in ids[1:]:
        result = client.post(
            base + "/source-dependence/relationships",
            json={
                "kind": "derived_from",
                "derived_source_id": derived,
                "upstream_source_id": ids[0],
                "reason": "Branch declaration",
            },
        )
        assert result.status_code == 201
    # Use the real bounded service with one root; report normally roots all task sources.
    report = client.get(base + "/report").json()
    monkeypatch.setattr(SourceDependenceService, "LIMITS", SourceDependenceLimits(**limit))
    response = client.post(
        base + "/source-dependence/projection", json={"root_source_ids": [ids[0]]}
    )
    assert response.status_code == 200, response.text
    projection = response.json()
    assert projection["truncated"] and projection["overflow_reason"] == reason
    report["source_dependence"] = projection
    page.route("**/report", lambda route: route.fulfill(json=report))
    page.locator("#refresh").click()
    expect(page.locator("#message")).to_contain_text("Report refreshed")
    page.get_by_text("Bounded dependence graph", exact=True).click()
    expect(page.locator("#dependence-boundary")).to_contain_text(reason)
    expect(page.locator("#dependence-boundary")).to_contain_text("do not establish independence")
    if reason == "edge_limit":
        expect(page.locator("#dependence-frontier")).to_contain_text("traversal remains incomplete")
    else:
        assert projection["frontier_omitted"]
        expect(page.locator("#dependence-frontier")).to_contain_text("omitted")
        if reason == "depth_limit":
            assert len(projection["frontier_source_ids"]) == 1
            expect(page.locator("#dependence-frontier")).to_contain_text(
                "additional frontier omitted"
            )
