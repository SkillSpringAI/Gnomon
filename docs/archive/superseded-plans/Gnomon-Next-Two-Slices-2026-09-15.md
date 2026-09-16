# Gnomon: current review and next two slices

Reviewed 15 September 2026 at local HEAD `928e80b52eb49bd74405244d856ed39a037a928e`.

This is a proposed follow-up plan to the superseded source-of-truth document, not a silent replacement of its slice numbering or authority. The architecture review is historical evidence pinned to `8a22052` and remains unchanged.

## Current assessment

Keep the architecture and finish hardening before activating Slice 13. Review covered both files in this directory, the latest ten commit summaries, the implementation/test changes since the architecture-review baseline, and the relevant current services, configuration, packaging and CI paths.

| Recent work | Assessment |
| --- | --- |
| `ff77cc8`: CI optional dependencies | Repaired. GitHub reports successful runs for this commit and `2d82596`. Minimal installation is also checked, although only by package import. |
| `6f0d3b0`: provider dispatch and cycle reconciliation | Adds DISPATCHED accounting, closes attempts on manual outcomes, passes configured bearer token limits, and fixes the missing-task exception. Provider lifecycle closure remains incomplete. |
| `7fe38d7`, `2d82596`: provider tests | Establish sequential dispatched-expiry protection and late completion. They do not overlap expiry selection with dispatch or race finalizers. |
| `928e80b`: atomic cycle startup | Activation and attempt insertion now share the repository transaction. Failure-injection regression passes. |
| Documentation commits | Improve historical accuracy, but the current gap statuses and acceptance checkboxes still need one evidence-backed reconciliation. |

## Remaining findings

1. **P1: expiry can still race dispatch.** `ProviderBudgetService.reserve()` selects expired PENDING rows without locking them, then updates the loaded records. `dispatch()` locks an attempt but does not take the task lock used by reservation. A reserving transaction can read PENDING, another transaction can commit DISPATCHED, and the first can overwrite it with EXPIRED and admit replacement work. This is a code-derived interleaving, not a reproduced concurrency result in this review.
2. **P1: finalization and recovery are incomplete.** `finish()` uses an ordinary read and unconditional ORM update, without a conditional transition or row lock. The route commits the success event separately from SUCCEEDED. A crash can leave a successful audit with a DISPATCHED attempt; no explicit reconciliation operation exists. The report-read transaction also spans provider execution. DISPATCHED conservatively retains capacity, but crashed calls can strand that capacity.
3. **P2: packaged migration discovery remains broken.** SQL remains outside package resources; package data includes only HTML. Empty migration discovery is accepted. The earlier wheel reproduction applies to these unchanged paths; it was not repeated here.
4. **P2: configured memory mode still creates a repository per request.** Separate create/get requests cannot share the task. The relevant construction is unchanged from the earlier reproduction.
5. **P2: arbitrary operator reasons still enter public audit events.** `MemoryService` copies full reason text into `change_reason`, despite the public event data-minimization contract.
6. **Verification gaps:** bearer configuration wiring and missing-task errors are fixed in code, but require regression tests through real dependency composition. Existing parity tests bypass constructors and do not assert outgoing token limits. CI runs migrations and pytest, but does not explicitly invoke the documented smoke, prototype, or authority-traceability scripts.

## Next slice 1: execution lifecycle closure (Slice 12A follow-up)

**Implementation update:** COMPLETE, 15 September 2026, on top of `928e80b`.
The canonical source of truth now records the implementation and verification:
278 tests passed, five opt-in browser tests skipped, static checks and fresh/upgrade
migrations passed, and smoke/HTTP restart/traceability checks passed. Unknown remote
outcomes retain capacity; recovery cannot assume non-execution or replay draft prose.
The findings above remain the dated pre-implementation review.

**Outcome:** a provider request cannot release capacity while dispatched work remains unresolved, and its terminal audit and attempt agree after concurrency or failure.

- Give reservation expiry, dispatch and completion consistent transaction ownership and lock ordering. Use conditional transitions and refresh records where necessary.
- Commit terminal attempt state and its correlated audit together; define idempotent repeated finalization and reject conflicting terminal outcomes.
- Materialize and validate the report, end the read transaction, then dispatch provider work. Document the durable boundary before dispatch.
- Define conservative recovery for unknown remote outcomes. Do not equate timeout or worker death with remote non-execution. Explicitly state whether limits count successful drafts, outstanding work, or all dispatches; the existing limit is not a monetary spending cap.
- Add PostgreSQL barrier tests for expiry-selection versus dispatch, concurrent finalizers, live delayed completion, failed validation after dispatch, and failure between provider return and finalization.
- Complete cycle-start/operator-recovery interleaving coverage for both runners and reconcile Slice 11 closure against that evidence.

**Exit gate:** competing requests cannot bypass the documented limit; terminal audit and attempt commit or roll back together; unknown outcomes have an audited recovery policy; stale cycle workers cannot overwrite operator outcomes or duplicate retained evidence.

## Next slice 2: installation, configuration and public-audit contracts (Slice 12B follow-up)

**Implementation update:** COMPLETE, 15 September 2026, on top of `928e80b`
and the Slice 12A working changes. The combined suite reports 296 passed and
five skipped browser tests. Clean-wheel base installation, concurrent migration
bootstrap, upgrade/rerun/drift checks, smoke, HTTP restart, static checks and
traceability pass. CI commands are updated; no hosted run is claimed. See the
canonical source of truth for the reconciled closure ledger and remaining gaps.

**Outcome:** supported installation and configuration paths preserve the same documented guarantees as the tested checkout.

- Package SQL migrations as resources and fail explicitly on missing resources. Test wheel installation outside the checkout, fresh migration, rerun, and existing-database upgrade. There were 19 migrations at review time and 20 after Slice 12A; derive the expected inventory from the source resources.
- Scope development memory storage to each application instance. Test create/get/start across requests and isolation between applications; retain the PostgreSQL requirement for evidence/report services.
- Validate provider names and numeric bounds at startup. Test the configured output-token limit through both credential paths and unknown-investigation draft requests returning 404 without provider execution.
- Keep complete operator reasons in governed history; emit only controlled categories and correlation IDs in public events. Test private prose and URL/credential-shaped strings against the public payload.
- Add the documented smoke/prototype/traceability checks to CI as appropriate and strengthen minimal/installed-package verification beyond a top-level import.
- Reconcile the current gap register with implementation, executable evidence, remaining risk and closure commit. Mark unsupported purge requirements as unsupported rather than inventing a production purge feature.

**Exit gate:** wheel and configured-application tests pass; public audit contains no arbitrary reason prose; CI enforces the documented gates; the source-of-truth ledger accurately records closures and remaining work.

After both slices, repeat the review gate and activate the existing **Slice 13: Security state machine**, followed by **Slice 14: Backup/restore conformance**. Keep live agent expansion deferred as already directed by the source of truth.

## Verification

- 112 unit tests passed.
- 35 focused PostgreSQL tests passed across reports, cycle recovery, and agent-cycle safety.
- Ruff passed; strict mypy passed for 72 source files.
- Authority traceability passed; this does not establish behavioral or release conformance.
- GitHub CI was successful at `2d82596`; local HEAD was one commit ahead of the local `origin/main` tracking reference. No CI result for `928e80b` was established.
- Full suite: **259 passed, 5 skipped** in 91.21 seconds. All five skips are the opt-in browser regression suite. No live provider calls or new concurrency reproduction were performed.

No implementation changes were made in this review. The pre-existing untracked architecture review was preserved.
