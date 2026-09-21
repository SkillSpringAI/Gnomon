"""Browser regression tests: RUN_BROWSER_TESTS=1; install Chromium first."""

import os
from urllib.parse import urlsplit

import httpx
import pytest
from test_source_cycle import source_cycle  # noqa: F401

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
            response = client.request(
                request.method,
                urlsplit(request.url).path,
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
    expect(page.locator("#cycles")).to_contain_text(
        f"Retained evidence ({1 if partial else 2})"
    )
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
