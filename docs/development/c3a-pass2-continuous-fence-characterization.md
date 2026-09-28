# C3a Pass 2 — Continuous-fence characterization and stopping finding

Date: 28 September 2026. Characterization only. No production code, schema, manifest, recovery policy, or mechanics extraction changed. This report follows [Pass 1](c3-reconstruction-mechanics-pass1.md) and [Pass 1B](c3-fail-closed-reconstruction-authority-design.md).

## Decision

**Candidate D does not survive unchanged.** The proposed early call to `AuthorityBootstrapService.initialize(RECOVERY)` creates a provisional pending fence under the pristine target's epoch P. Bootstrap itself inserts no epoch-bearing audit row, but existing trusted services can capture a RecoveryContext and issue operator and execution authorizations against that provisional basis before import or provenance finalization. Those records and audits persist with P. Replacing canonical epoch P with manifest epoch E would leave valid historical records for an incident that describes the empty/provisional target, stale for the reconstructed target. More seriously, the existing recovery path could be entered on the provisional basis before restored data has been validated. The repository does not enforce an exclusive-target invariant that rules out another local process using those services. Do not encode a test that assumes no such records can exist, and do not implement the P→E rewrite as a safe standalone transition.

`AuthorizationService.require_current_execution()` also does not check the pending fence or verify that its context ID resolves to a freshly captured current context. It checks epoch, expiry, identity, supplied context ID and capability; a still-unexpired same-epoch execution record can be returned while pending. This helper alone is not an effect authorization. Protected restoration separately checks a current context, reconciliation and authorization binding. Therefore the broad claim “historical authorization is rejected solely by the fence” is false at the helper boundary; the narrower downstream guarded-effect claim remains the existing contract.

## Characterization performed

Two new integration tests were added to `test_database_reconstruction_integration.py`:

- The data-producing restore runner reads the **committed** target singleton immediately before its import call. Current orchestration exposes pristine `NORMAL`/v1/pending=false there. This is a database-observed ordering check, not only a mocked call-order assertion. Future fence-before-import work must invert this observation and use a real `pg_restore` drill as a second check.
- On a disposable migrated target, early `RECOVERY` bootstrap yields effective `RECOVERY_REQUIRED`, pending=true, raw `NORMAL`/v2/P, origin `NORMAL`/v1, and no epoch-bearing rows created by bootstrap. It then proves that `RecoveryContextService.capture()`, `AuthorizationService.issue_operator()`, and `issue_execution()` can create contexts/grants/audits under P while the fence is pending.

A new authorization integration test pins that a same-epoch execution record issued before the fence is still returned by `require_current_execution()` after bootstrap when time, context ID and capability match. This is characterization of the helper's bounded contract, not a desired authorization for effects.

Existing Pass 1 tests cover the current after-restore unfenced state and post-import failure residues. Existing reconstruction tests cover all `SecurityState` values at the current mechanics seam, including a source-pending manifest; the full workflow's recovery test covers `NORMAL`, `DEGRADED`, `LOCKDOWN` and `RECOVERY_REQUIRED`. `COMPROMISED_SUSPECTED` is covered at the mechanics seam but should be added to the future finalized-basis matrix. Existing capture-failure coverage pins that a committed bootstrap fence persists. The real M2 drill covers baseline and restrictive fixtures.

## Proposed state matrix and what remains untested

Let S/V/E be validated manifest state, version and epoch; P is the pristine target epoch. The following is the **intended** provenance relation, not a passing production behavior or a simulated finalization test:

| Source input | Required finalized state before context capture |
| --- | --- |
| S = `NORMAL`, V ≥ 1, E non-nil, source pending=false | Raw S; origin S/V; current version V+1; E; pending=true; effective `RECOVERY_REQUIRED`. |
| S = `DEGRADED`, `COMPROMISED_SUSPECTED` or `LOCKDOWN`, V ≥ 1, E non-nil | Same relation; raw and origin state equal the particular restrictive S. |
| S = `RECOVERY_REQUIRED`, V ≥ 1, E non-nil, source pending=false or true | Same relation with a **new** target bootstrap incident. Source origin/timestamp are not in the manifest and cannot be reused. |
| Unsupported state, nil E, V < 1, malformed pending value | Existing manifest/domain validation rejects before import; retain that behavior. |

Version examples V=1, V=3 and V=7 matter: current V+1 must be greater than origin V even when a provisional bootstrap already used target v2. Epoch E may differ from P. No finalization operation exists yet, so atomicity, the all-state finalized matrix, and the pre-import failure matrix cannot honestly be claimed as tested. They are required C3a implementation contracts.

## Epoch-transition evidence

Bootstrap uses a row lock and commits a change to `security_state`; it does **not** append `security_state_transitions` or other epoch-bearing audit/history rows. On an otherwise empty migrated target, all tables with an `authority_epoch_id` column remain empty immediately after bootstrap. The singleton row is the only persisted P-bearing value from bootstrap itself.

That observation is not enough to justify replacing P. A pending provisional basis is accepted by `RecoveryContextService.current_basis()` and `capture()`. Context, context audit, operator authorization, execution authorization and authorization audit rows can then carry P. Their own stored commands and audits remain internally coherent if P becomes historical, but they describe an incomplete provisional incident, and the canonical E switch makes them stale rather than transforming them into valid reconstruction evidence. A live service could also attempt governed recovery using that provisional context before import. Existing database constraints permit P→E on the singleton; the **service-level evidence and lifecycle contract** is the conflict. Candidate D assumed no provisional evidence without enforcing that assumption.

## Failure matrix

| Failure point | Current behavior/evidence | Required property for a revised design |
| --- | --- | --- |
| Before early-fence commit | Current preflight/planning leaves pristine `NORMAL`/v1/P; no restored data. | Unchanged target is acceptable. |
| Immediately after early-fence commit | Characterized raw `NORMAL`/v2/P, pending=true, effective `RECOVERY_REQUIRED`; no bootstrap audit, but provisional context/authorization creation is possible. | No ordinary authority and no consumable premature recovery evidence. |
| During/after `pg_restore` | Current orchestration has no early fence; Pass 1 showed a committed import can precede authority fencing. Failed child transaction itself rolls back. | Fence must commit before import; durable import or failed import must remain fail-closed. |
| During authority finalization | No such operation exists. Current separate authority write can commit S/V/E with pending=false. | Atomic historical provenance and fence; failure retains pre-import restrictive state. |
| During migration | Current post-import failure can leave S/V/E unfenced. | Retain restrictive state despite independently committed migration steps. |
| During post-restore validation | Current failure can leave S/V/E unfenced. | Retain restrictive state. |
| During context capture | Existing test proves bootstrap fence persists on capture failure. | Capture only against finalized, validated basis; failure retains fence and reports no fresh context. |

Discard/recreate remains the preferred public recovery model; no evidence requires resumability or weakening pristine-target preflight. A target after early fencing should not be silently treated as a fresh attempt even if no data has yet imported.

## Fresh-context and M2 implications

Current `_enter_recovery()` captures after `_restore_verified_data()` returns, so on the successful current path its basis is source-derived and fenced. That ordering is already covered by reconstruction tests. Moving bootstrap before import creates an additional provisional basis that current `capture()` accepts; therefore “capture only after finalization and validation” is **not** guaranteed by early bootstrap alone.

The M2 helper compares the source and target `security_epoch` group, including the raw singleton row (excluding `updated_at`), before recovery bootstrap. A continuously fenced design cannot retain that exact unfenced comparison point. Preserve all other deterministic projection groups, snapshot and report comparisons. Replace only the raw singleton equality with assertions of S/V/E provenance, origin S/V, current V+1, pending=true and effective `RECOVERY_REQUIRED`; keep security transition-history comparison. The real `pg_dump`/`pg_restore` drill must run against the finalized fenced target and still exercise baseline and restrictive/unresolved variants. Production inspection must check the finalized basis without claiming full M2 semantic equivalence.

## Smallest alternatives to resolve before Pass 3

1. **Avoid the P→E transition:** atomically install manifest S/V/E with a pending recovery fence **before** import, then keep it pending. This removes provisional-epoch orphaning, but the resulting valid E-basis could still be captured and used before import; it needs an enforceable “reconstruction incomplete” gate or exclusive-target guarantee before it is safe.
2. **Existing restrictive non-pending state before import:** set the canonical row to `RECOVERY_REQUIRED` with no pending bootstrap, then atomically establish source-derived pending bootstrap after validation. Current context capture/restoration reject a non-pending basis, but authorization issuance can still write provisional-epoch rows. This changes the requested early-**existing-fence** contract and needs explicit authority/history analysis.
3. **Enforced exclusive target:** make reconstruction the only service able to connect to the target until provenance finalization and validation. A process-local lock or advisory lock not observed by context/authorization services is insufficient. No such invariant is currently enforced or documented as part of the service contract.

These are comparison candidates, not implementation approval. **There is no safe exact C3a Pass 3 code patch selected yet.** The smallest next design decision is how to prevent pre-validation recovery-context/grant creation (or enforce exclusive target access) while keeping restored data fail-closed. Only after that decision should Pass 3 specify the final authority write and failure tests. Do not begin C3b extraction.

## Verification

Focused reconstruction and authorization integration suites: 30 passed, 2 environment-dependent skips. Authority-bootstrap, recovery-context, manifest and reconstruction-unit suites: 51 passed. Ruff lint and format checks for changed test files and `git diff --check` passed. Pass 1 changes remain in the working tree; no production files changed during Pass 2.
