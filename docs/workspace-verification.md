# Workspace verification

Run `python scripts/verify_prototype.py --serve` with the local PostgreSQL service
available. Open the printed Browser QA URL. The database and investigations created
by this command are disposable; Ctrl+C shuts down the server and removes that database.

1. Confirm the initial report loads, Run is enabled, and Plan is disabled for the
   already-planned first cycle.
2. Pause the investigation. Run and Plan should be disabled. Resume and verify Run
   becomes available again.
3. Run cycle 1. Action buttons are disabled while the request is pending. Verify a
   completed outcome, two observations, unverified claims, and unresolved objectives.
4. Plan the next cycle, run it, and reload the page. Verify both cycle outcomes and
   four total sources remain visible. The next-plan button should be available.
5. Generate a draft. Verify the draft appears as plain text with its provider/model.
6. To check stale-state handling, pause the disposable investigation through the API
   docs in a second tab while the workspace still shows active. Attempt to plan from
   the stale workspace. It should show the conflict and reload paused controls.
7. To check an active cycle, resume and plan/start a cycle using the API docs without
   running it. Refresh the workspace: Run and Plan should both be disabled. Record a
   blocked outcome with unresolved objectives through the API and refresh again.
   Confirm the outcome, unresolved work, and available next-plan control.
8. Stop the verification server with Ctrl+C while the workspace is open. Refresh the
   report using its button. Actions should be disabled, status unavailable, and the
   error should explain that displayed history may be stale.

Verified on 2026-09-13 in the Codex in-app browser against the actual loopback server:
pause/resume, two cycles, page reload, draft generation, stale-state conflict, active
cycle guards, blocked outcome display, and unavailable-server handling. The automated
command separately verifies all numbered migrations and report persistence after server
restart. This is a browser QA procedure, not an automated browser regression suite.

## Source collection and objective selection

For a planned cycle, select one to three local-agent objectives or enter one or two
HTTP(S) URLs with an objective for each. Source domains must already be enabled through
the existing registry API. Confirm empty/invalid inputs prevent submission, controls
disable during collection, and results show source/claim associations under
"Evidence by objective". Reload to verify persistence; plan another cycle to verify
old input selections reset. Pause/resume preserves inputs for the same planned cycle.

Automated browser regression tests use headless Edge on Windows (Chromium elsewhere),
the real FastAPI application and PostgreSQL, and controlled HTTP source responses.
No live source websites are contacted. Install the optional dependencies and run:

```powershell
python -m pip install -e ".[dev,browser]"
# On machines without Edge: python -m playwright install chromium
# Then set PLAYWRIGHT_CHANNEL=chromium for that browser.
$env:RUN_BROWSER_TESTS = "1"
python -m pytest tests/integration/test_workspace_browser.py
```

Coverage includes exact objective/URL payloads, successful and partial collection,
busy controls, invalid URLs, stale-state recovery, reload, unavailable reports, and
narrow-screen layout. Set `WORKSPACE_SCREENSHOT` to an absolute PNG path to capture
the rendered cycle history. Browser tests are skipped unless explicitly enabled.

## Objective review

After collection finishes, review the latest cycle before planning another. Select an
objective, choose a decision, and enter a rationale. Completing a review requires a source
or claim reference. Save, reload, and inspect Objective review history. Record an unresolved
correction and verify both revisions remain. Add evidence through a second client before
submitting an older form; it must reject the stale submission and refresh the report.
Previously completed reviews show "evidence changed" when their evidence basis is stale.
The browser regression suite covers this workflow with the real API and database.

## Interrupted-cycle recovery

Refresh an active cycle to see its retained progress and recovery form. Enter a reason
and close the cycle. Verify a failed outcome retains its IDs, the active investigation
becomes paused, and reload preserves the result. Resume explicitly before planning.
Recovery requests using an older progress fingerprint must refresh before retrying.
Untracked legacy/manual cycles display an explicit incomplete-association notice.

Recovery integration tests terminate a real worker process after source/claim commits,
verify atomic progress retention, reject concurrent/stale recoveries, and fence late
returns from both source and agent runners after resume. The browser suite covers
recovery form validation, stale state, reload, and continuation.
