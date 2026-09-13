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
command separately verifies all seven migrations and report persistence after server
restart. This is a browser QA procedure, not an automated browser regression suite.
