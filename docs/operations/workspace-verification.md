# Workspace Verification

Run `python scripts/verify_prototype.py --serve` with the local PostgreSQL service available, then open the printed Browser QA URL. The database and investigations created by this command are disposable; Ctrl+C shuts down the server and removes that database.

## Core browser procedure

1. Confirm the initial report loads, Run is enabled, and Plan is disabled for the already-planned first cycle.
2. Pause the investigation. Run and Plan should be disabled. Resume and verify Run becomes available again.
3. Run cycle 1. Confirm a completed outcome, two observations, unverified claims, and unresolved objectives.
4. Plan and run the next cycle, reload the page, and verify both cycle outcomes and four total sources remain visible.
5. Generate a draft and verify it appears as plain text with its provider/model.
6. Through API docs in a second tab, pause the investigation while the workspace remains active. Attempt to plan from the stale workspace and confirm the conflict reloads paused controls.
7. Start a cycle through API docs without running it. Refresh the workspace and confirm Run and Plan are disabled. Record a blocked outcome and verify the unresolved work and next-plan control.
8. Stop the verification server, refresh the report, and confirm actions are disabled, status is unavailable, and the error explains that displayed history may be stale.

The procedure was verified on 2026-09-13 in the Codex in-app browser against the loopback server. Automated verification separately checks all numbered migrations and report persistence after server restart. This is browser QA, not an automated browser regression suite.

## Automated browser tests

Install the optional dependencies and run:

```powershell
python -m pip install -e ".[dev,browser]"
# On machines without Edge: python -m playwright install chromium
# Then set PLAYWRIGHT_CHANNEL=chromium for that browser.
$env:RUN_BROWSER_TESTS = "1"
python -m pytest tests/integration/test_workspace_browser.py
```

The browser suite covers exact objective/URL payloads, successful and partial collection, busy controls, invalid URLs, stale-state recovery, reload, unavailable reports, narrow-screen layout, objective review, and interrupted-cycle recovery. Tests are skipped unless explicitly enabled.
