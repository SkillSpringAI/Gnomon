# Gnomon Hardening and Development Source of Truth

**Repository:** `SkillSpringAI/Gnomon`\
**Baseline reviewed:** `928e80b` plus Slice 12A/12B working changes, 15 September 2026\
**Purpose:** Canonical plan for closing identified gaps, preventing
regressions, and sequencing the next development slices.

> **Rule:** Treat this document as the implementation source of truth
> until an explicitly reviewed revision supersedes it. If code, an older
> gap document, or an informal plan conflicts with this file, reconcile
> the conflict rather than silently choosing one.

## 1. Current assessment

Gnomon has a strong architectural base. The immediate risks are
persistence and audit invariants, historical-state reconstruction,
concurrency and budget accounting, crash recovery, workflow
state-machine correctness, database enforcement, migration integrity,
backup/restore verification, CI enforcement, and future external-agent
boundaries.

Preserve the existing separation between domain, application, ports,
adapters, persistence, security, and API layers.

### Architectural invariant

External models, agents, and sources may produce **observations,
evidence, or proposals**. They do **not** gain authority to mutate
governed state merely by producing them.

``` text
External systems / models / agents
              |
           adapters
              |
            ports
              |
         application
              |
     governance/security
              |
         persistence
```

## 2. Priority definitions

  -----------------------------------------------------------------------
  Priority                            Meaning
  ----------------------------------- -----------------------------------
  **P0**                              Integrity/security defect that can
                                      undermine a core Gnomon guarantee.
                                      Fix before expanding capabilities.

  **P1**                              Significant
                                      correctness/recovery/concurrency
                                      gap. Fix before live external-agent
                                      expansion.

  **P2**                              Hardening or maintainability
                                      improvement to complete before
                                      serious beta/release.

  **P3**                              Useful improvement that can follow
                                      core hardening.
  -----------------------------------------------------------------------

A gap is closed only when its invariant is documented, implementation
exists, positive and negative tests pass, concurrency is tested where
relevant, migrations are handled, CI runs the checks, and documentation
is updated.

# 3. Gap register

## Current closure ledger (Slice 12B reconciliation)

This table distinguishes implementation from executable evidence and remaining
work. Working-tree closures are not commit IDs or claims of hosted CI success.

| Gap | Current implementation/evidence | Remaining work | Closure reference |
| --- | --- | --- | --- |
| 001 retention | Archive retains audit and attributable memory; direct SQL rejects retained-task deletion | Production physical purge is unsupported, not a missing feature | `63da8b0`; archive verification in 12B working changes |
| 002 reconstruction | Target/version history, reversal and provenance tests pass | Compatibility policy for future/older journal formats remains open | Core implementation `f3fbaa8`; no full closure |
| 003 assertions | Governed persistence validation uses explicit exceptions; two derived-fingerprint assertions remain programmer-only | None in reviewed invariant paths | `f3fbaa8` |
| 004 provider lifecycle | Controlled PostgreSQL contention, terminal audit atomicity and UNKNOWN recovery pass | Unknown outcomes retain capacity; no monetary cap or automatic retry | 12A working changes |
| 005 cycle attempts | Startup rollback, operator closure, process interruption and late evidence tests pass | Future live networks need their own recovery evidence | `928e80b` plus 12A tests |
| 006 workflow boundaries | README documents short provider transactions and retained cycle artifacts; interruption/transaction tests pass | Explicit retained-evidence UI presentation remains an observability follow-up | Partial; no full closure |
| 007 DB enforcement | SQL constraints, checksums and direct-invalid-SQL tests exist | Complete invariant inventory and consistent database-error translation | `63da8b0`; no full closure |
| 008 migration integrity | Installed wheel: resource hashes, concurrent bootstrap, populated upgrade, rerun and historical drift rejection pass | Migration downgrades remain deferred | `63da8b0` plus 12B working changes |
| 009 backup/restore | Not implemented | Backup/restore fixture and state/history comparison (Slice 14) | Open |
| 010 CI | Quality, PostgreSQL, smoke, prototype, traceability and clean-wheel commands are configured and locally verified | Hosted execution of the working changes still pending; browser suite opt-in | `ff77cc8` plus 12B workflow |

Architecture-review findings F1–F8 are now addressed in code: F1 in `ff77cc8`,
F2/F3 in `928e80b` plus 12A, and F4/F5/F8 in 12B. F6/F7 were repaired in
`6f0d3b0`; 12B adds real configuration-path tests and rejects unknown tasks before
provider construction. The dated review remains historical evidence, not the
current defect list.

## GAP-001: Audit retention semantics

**Priority:** P0/P1\
**Status:** CLOSED for supported archive/retention policy (15 September 2026)

**Original problem:** Event retention was coupled to task deletion. Migration 013
now rejects deletion of tasks with retained audit events, and migration 014 adds
the archive lifecycle. The governed memory journal remains attributable by task ID.

**Invariant:** Deleting or archiving operational state must not silently
destroy authoritative history.

-   [x] Define canonical task lifecycle using archive/logical deletion
    instead of ordinary physical deletion.
-   [x] Review every FK from historical/audit tables for `ON DELETE`
    behaviour.
-   [x] Prevent accidental deletion of tasks owning retained history.
-   [x] Define whether historical records may ever be physically purged.
-   Not applicable: no production physical purge is supported. Any future purge
    requires a separately reviewed governed/audited operation. Fixture cleanup is test-scoped.
-   [x] Align `research_events` and `memory_changes` retention semantics
    deliberately.
-   [x] Add direct-database retention tests.

**Acceptance:** archive retains events and attributable memory
(`test_task_archive_retains_events_and_attributable_memory`); direct SQL deletion
of a task with retained events is rejected (`test_persistence_invariants.py`).

## GAP-002: Historical epistemic-state reconstruction

**Priority:** P0/P1\
**Status:** PARTIAL — historical APIs implemented; journal-format compatibility remains open

**Original problem:** Historical state was not queryable. Target history and
version APIs now exist; compatibility across future journal-format changes is
still an explicit outstanding requirement.

**Invariant:** For every governed mutation, Gnomon can explain what
state existed, what changed, why, who/what requested it, and the
resulting state.

-   [x] Define `MemoryChangeRecord` as the canonical historical journal.
-   [x] Keep live claim/assessment tables as current-state projections.
-   [x] Implement history retrieval by target.
-   [x] Implement reconstruction/retrieval by version.
-   [x] Verify create/update/archive/logical-delete/restore/reverse
    histories.
-   [x] Reconstruct historical provenance links.
-   [ ] Define compatibility behaviour for old journal formats.

Candidate API:

``` text
GET /investigations/{task_id}/memory/{target_id}/history
GET /investigations/{task_id}/memory/{target_id}/versions/{version}
```

**Acceptance** - \[ \] Create -\> update -\> archive -\> restore yields
the expected version sequence. - \[ \] Reversal reconstructs pre-change
and post-reversal state. - \[ \] Current projection equals latest valid
reconstructed state. - \[ \] Historical evidence/provenance matches the
selected version.

## GAP-003: Python assertions used for persistence/domain invariants

**Priority:** P1/P2\
**Status:** CLOSED for reviewed governed paths (`f3fbaa8`)

**Invariant:** Conditions protecting persisted or governed state use
executable validation, not `assert`.

-   [x] Search `src/` for `assert`.
-   [x] Classify each as programmer-only, domain, persistence, or
    external-input validation.
-   [x] Replace domain/persistence/input assertions with explicit typed
    exceptions.
-   [x] Keep assertions only where their removal cannot alter authority
    or persisted correctness.
-   [x] Add negative tests.

Prefer:

``` python
if record is None:
    raise MemoryConflict("Expected governed record was not created")
```

over `assert record is not None` when correctness depends on it.

## GAP-004: Concurrent provider/report budget race

**Priority:** P1\
**Status:** CLOSED for the documented draft-count policy (Slice 12A, 15 September 2026)

**Invariant:** Provider budget authorization and reservation are atomic.
Concurrent requests cannot collectively exceed the configured limit.

Implemented attempt states:

``` text
PENDING
DISPATCHED
UNKNOWN
SUCCEEDED
FAILED
EXPIRED
```

-   [x] Define persistent generation attempt/reservation.
-   [x] Add operation/request ID.
-   [x] Atomically authorize and reserve capacity.
-   [x] Perform remote call outside the reservation transaction.
-   [x] Define failure/refund and timeout/expiry semantics.
-   [x] Make retries idempotent.
-   [x] Audit attempted/rejected/failed/successful calls distinctly.
-   [x] Add simultaneous-request integration tests.
-   [x] Fence dispatched in-flight attempts from expiry refunds.
-   [x] Reconcile uncertain late provider outcomes.
-   [x] Add controlled live-expiry/finalization interleaving tests.

All writers lock task then attempt and refresh state. Terminal attempt/audit writes
are atomic; identical finalizations are no-ops and conflicting outcomes are rejected.
`UNKNOWN` retains capacity after transport/adapter errors or operator recovery of
an overdue dispatch. A late known result may finalize it; no timeout-only refund or
automatic retry is supported. This counts successful drafts plus outstanding or
uncertain work, not monetary spend or every dispatch. Known validation failures
and undispatched expiry release capacity. See `tests/integration/test_provider_lifecycle.py`.

**Acceptance** - [x] Two requests competing for one remaining slot
authorize exactly one. - [x] Failed calls follow documented budget
semantics. - [x] Same operation ID cannot double-consume budget. - [x]
Expired pending attempts recover safely.

## GAP-005: Cycle execution is becoming an implicit state machine

**Priority:** P1\
**Status:** CLOSED for the bounded runners (Slice 12A verification, 15 September 2026)

**Invariant:** Every externally meaningful cycle execution has an
identifiable attempt and recoverable persisted stage.

Candidate stages, to be minimized during design:

``` text
CREATED
STARTED
DISCOVERING
QUESTIONING
EVIDENCE_RECORDED
EXTRACTING_CLAIMS
FINALIZING
COMPLETED
BLOCKED
FAILED
INTERRUPTED
```

-   [x] Introduce persistent cycle execution/run ID.
-   [x] Define minimum useful persisted stages.
-   [x] Link evidence, claims and outcomes to the attempt where useful.
-   [x] Define restart/recovery semantics per stage.
-   [x] Prevent recovered processes duplicating committed evidence.
-   [x] Preserve manual operator outcomes over automated recovery.

**Interruption evidence:** `test_cycle_recovery.py` covers operator closure before
attachment, startup rollback, process death after source/claim commit, and late
results after recovery. `test_agent_cycle_safety.py` and `test_source_cycle.py`
cover adapter interruption, guards before evidence persistence, retained partial
results, and failed final-outcome writes. These establish the bounded-runner
policy; they do not claim recovery for future live agent networks.

## GAP-006: Workflow atomicity must remain explicit

**Priority:** P1/P2\
**Status:** OPEN, documentation/test hardening

**Invariant:** Successfully persisted evidence is not discarded merely
because a later cycle phase fails.

-   [x] Document transaction boundaries.
-   [x] Document why network/provider work must not hold long DB locks.
-   [x] Document which intermediate artifacts survive failure.
-   [x] Add regression tests preventing a future giant-transaction
    refactor.
-   [ ] Clearly identify retained evidence in failed-cycle responses/UI.

## GAP-007: Critical invariants rely too heavily on application validation

**Priority:** P1/P2\
**Status:** OPEN

**Invariant:** Irreversible or authority-critical constraints are
enforced at the lowest practical layer.

Evaluate DB constraints such as:

``` sql
CHECK (version >= 1)
CHECK (confidence >= 0 AND confidence <= 1)
CHECK (strength >= 0 AND strength <= 1)
CHECK (lifecycle IN ('active', 'archived', 'logically_deleted'))
```

-   [ ] Inventory application invariants.
-   [ ] Classify application-only vs DB-critical.
-   [x] Add DB constraints for critical invariants.
-   [x] Add migration.
-   [x] Add deliberately invalid direct-SQL tests.
-   [ ] Keep application errors understandable when DB constraints
    reject writes.

## GAP-008: Migration immutability/checksums

**Priority:** P1/P2\
**Status:** CLOSED for forward migrations (Slice 12B)

**Invariant:** An applied migration version identifies immutable
migration content.

**Slice 12B repair:** tracking-table initialization now takes the same advisory
lock as migration application. The installed-wheel check verifies two simultaneous
first-time installers, preserving exactly one application of every migration.

-   [x] Add SHA-256 checksum to migration tracking.
-   [x] Calculate checksum before application.
-   [x] Store version + checksum + applied timestamp.
-   [x] Compare applied checksum with current migration file.
-   [x] Fail closed on mismatch.
-   [x] Test modified historical migration.
-   [x] Document: never edit an applied migration; add a new one.

**Acceptance:** clean schema, populated upgrade, idempotent rerun, modified-file
rejection, and concurrent runners are verified by `scripts/verify_wheel.py --database`.
Fresh application HTTP/restart checks additionally use `scripts/verify_prototype.py`.

## GAP-009: Backup and restore conformance

**Priority:** P1\
**Status:** OPEN

**Invariant:** Supported backup/restore reproduces investigation state,
history, provenance, versions, audit records and deterministic derived
snapshots.

``` text
construct investigation
-> add evidence/claims/assessments/history
-> deterministic snapshot
-> backup
-> destroy/recreate DB
-> restore
-> reproduce snapshot
-> compare
```

-   [ ] Define supported PostgreSQL backup process.
-   [ ] Define restore process.
-   [ ] Build automated recovery fixture.
-   [ ] Compare IDs, versions, provenance, audit, memory journal and
    hashes.
-   [ ] Verify ephemeral provider credentials are not accidentally
    persisted.
-   [ ] Add recovery verification to release checklist.

## GAP-010: CI must enforce repository guarantees

**Priority:** P1\
**Status:** IMPLEMENTED and locally verified; hosted CI for working changes pending

**15 September Slice 12A verification finding (P2):** `scripts/smoke_test.py`
completed its workflow but failed fixture cleanup against migration 013's audit
retention FK. Its isolated test history must be explicitly removed before its
fixture task; production retention must remain enforced. Repair and rerun are
complete and the smoke check passes. Slice 12B adds the expanded verification commands to CI.

Required gates:

``` text
ruff
mypy --strict
unit tests
PostgreSQL integration tests
migration from zero
migration integrity/checksum tests
smoke test
prototype/conformance verification
```

-   [x] Verify current GitHub Actions state.
-   [x] Add/repair CI if absent or incomplete.
-   [x] Pin supported Python/PostgreSQL versions appropriately.
-   [x] Fail PR/main checks on gate failure.
-   Deferred unless PR latency becomes excessive: split slower integration checks.

# 4. Python-specific review checklist

-   [ ] `assert` used as validation.
-   [ ] Mutable default arguments such as `def f(items=[])`.
-   [ ] Bare `except:`.
-   [ ] Broad `except Exception` without deliberate rollback/recovery.
-   [ ] `Any` leaking across domain/authority boundaries.
-   [ ] Raw dictionaries where a typed model should define the contract.
-   [ ] `Optional`/`None` without explicit handling.
-   [ ] Naive datetimes instead of timezone-aware UTC.
-   [ ] Mutation after validation bypassing invariants.
-   [ ] SQLAlchemy objects used unexpectedly after session lifecycle.
-   [ ] `flush()` vs `commit()` assumptions.
-   [ ] ORM object-state assumptions after `rollback()`.
-   [ ] Truthiness checks where explicit enum/state comparison is safer.
-   [ ] JSONB changes without migration/backward compatibility.
-   [ ] Network/provider work while holding unnecessary DB locks.
-   [ ] Iterator/generator exhaustion when reused.
-   [ ] Shared mutable class/dataclass/Pydantic state.
-   [ ] Blocking sync I/O in async FastAPI paths.
-   [ ] Exceptions/logs exposing secrets or raw sensitive provider
    responses.
-   [ ] Unsafe path handling if local file ingestion expands.

# 5. Development slices

## Slice 10A: Historical authority hardening

**Goal:** Make governed history explicit, reconstructable and
independent of runtime assertions.

**Status:** COMPLETE (14 September 2026). Target history and version
reconstruction are exposed through the memory API, journal chains are
validated before being returned, and governed persistence assertions have
been replaced with explicit failures. The two remaining source assertions
are programmer-only postcondition checks for an in-memory derived
fingerprint.

-   [x] Historical target/version retrieval.
-   [x] Deterministic reconstruction tests.
-   [x] Replace authority/persistence assertions.
-   [x] Document live projection vs historical journal.
-   [x] Verify reversal history.
-   [x] Update API/docs.

**Exit gate:** A reviewer can explain a claim/assessment's complete
state evolution without manually inspecting raw DB rows.

## Slice 10B: Persistence invariant hardening

**Goal:** Make the database defend core invariants.

**Status:** COMPLETE (14 September 2026; CI dependency-path repair completed
15 September 2026). Migration 012 adds journal version
and operation checks, migration tracking records SHA-256 checksums and rejects
drift, migration 014 adds the governed archive state, direct SQL tests cover
invalid journal writes and retained-audit deletion, and CI runs the required
quality/integration gates with the AWS optional dependencies available to
strict mypy. A separate minimal-install job verifies the base package without
optional AWS dependencies. No production physical-purge operation is
supported; fixture purging is explicit and test-scoped.

-   [x] Audit/task retention policy.
-   [x] FK deletion review.
-   [x] Critical SQL CHECK constraints.
-   [x] Migration checksums.
-   [x] Direct-invalid-SQL tests.
-   [x] CI enforcement.

**Exit gate:** A direct SQL client cannot trivially violate core
lifecycle/version/range/history guarantees.

## Slice 11: Persistent execution attempts and crash recovery

**Goal:** Turn cycle execution into an explicitly recoverable workflow.

**Status:** COMPLETE (Slice 12A verification, 15 September 2026; artifact
linkage follow-up completed 15 September 2026). Migration 015 and both cycle
runners persist a unique execution attempt with durable stage/status
transitions, including terminal completion/failure state. Operator recovery
closes interrupted attempts with an auditable reason; stale and duplicate
recovery is fenced by the existing compare-and-set recovery contract.
The follow-up records committed source and claim IDs on each attempt.
The architecture review identified startup and manual-outcome races; both are
now transactionally reconciled and covered by PostgreSQL integration tests.
Both runner entry points now have failure-injection coverage for attempt insertion
and controlled operator recovery/manual outcome between activation and attachment.
Existing interrupted-process and late-evidence tests verify retained artifacts and
fencing after recovery/resume.

-   [x] Cycle run/attempt identity.
-   [x] Minimal persisted execution stages.
-   [x] Restart/recovery policy.
-   [x] Interruption test matrix.
-   [x] Idempotent recovery.
-   [x] Operator-visible recovery reason.
-   [x] Atomic activation and attempt creation boundary.
-   [x] Manual outcome closes a still-running attempt.

**Exit gate:** Every simulated crash safely resumes, safely terminates,
or explicitly requires operator recovery without silent
duplication/loss.

## Slice 12: Provider budget and concurrency governance

**Goal:** Make remote-provider use deterministic under
concurrency/retries.

**Status:** Slices 12A and 12B COMPLETE (15 September 2026), with hosted CI pending
for the working changes. Provider lifecycle writes now share task-first lock ordering,
refresh state under lock, and commit final state and audit together. Migration 020
adds conservative `UNKNOWN` recovery. Report reads end before dispatch/provider
execution. Controlled PostgreSQL tests cover expiry/dispatch ordering, competing
finalizers, late completion after recovery, invalid results, transport failures,
audit rollback, and cross-task operation-ID collisions.

-   [x] Atomic reservation.
-   [x] Generation attempt state.
-   [x] Idempotency key/operation ID.
-   [x] Timeout/expiry handling.
-   [x] Retry semantics.
-   [x] Concurrent integration tests.
-   [x] Provider adapter parity tests.

**Exit gate:** Concurrency cannot bypass configured provider limits.

### Slice 12A completion evidence

- Full suite: **278 passed, 5 skipped** (opt-in browser suite).
- Ruff and strict mypy: pass (72 source files).
- Existing database: migration 020 applied; rerun applies zero migrations.
- Fresh database: all 20 migrations applied; rerun is a no-op.
- Prototype HTTP lifecycle/restart verification, smoke test, and authority
  traceability: pass. Traceability is not full behavioral/release conformance.
- No live provider calls were made. Verification is local, based on `928e80b`
  plus the Slice 12A working changes; hosted CI for these changes is not claimed.

### Slice 12B completion evidence

- Canonical migrations are package resources in `src/research_agent/migrations/`.
  All 20 files retain their bytes/checksums. No new SQL migration was needed for 12B.
- `scripts/verify_wheel.py --database` passes from a clean base virtual environment
  outside the checkout: installed import identity, resource inventory/checksums,
  memory API isolation without AWS, concurrent migration bootstrap, populated
  upgrade, rerun, modified-history rejection, workspace resources and stub drafting.
- `tests/unit/test_configuration_contracts.py` covers configured task lifetime,
  app isolation, startup bounds/provider validation, and disabled-budget status.
- `tests/integration/test_provider_configuration.py` verifies outgoing token limits
  of 1 and 100 for both credential transports, and missing-task 404s before any
  provider construction or attempt insertion.
- Public memory events now contain controlled reason categories and correlation
  IDs. Full reasons remain in governed history. New writes reject arbitrary public
  reason prose; the public read projection sanitizes legacy reasons without
  rewriting retained rows. Existing DB files/backups can retain historical text.
- Full suite: **296 passed, 5 skipped**, with two Pydantic alias warnings in
  concurrency tests. Ruff and strict mypy pass (72 source files).
- Existing-database migration rerun, smoke, fresh 20-migration database,
  real HTTP lifecycle/restart, and authority traceability pass.
- CI now invokes smoke, prototype, traceability and clean-wheel verification.
  Hosted results remain pending until these working changes are committed/pushed.

The exit review closes the eight dated architecture findings for their reviewed
scope and preserves the remaining gaps in the current ledger. The next planned
development slice is **Slice 13: Security state machine**, subject to the review
gate below. This is not full authority/release conformance or authorization to
expand live agent networking.

## Slice 13: Security state machine

**Goal:** Implement explicit operational security states.

The canonical state names and structural transition table are defined in
[Slice 13 Security State Model and Transition Table](Slice%2013%20Security%20State%20Model%20and%20Transition%20Table.md).
Slice 13 is decomposed into independently reviewable increments; 13.1 covers
only the pure domain model and transition legality, before persistence,
authorization, or API behavior changes.

Candidate states:

``` text
NORMAL
DEGRADED
COMPROMISED_SUSPECTED
LOCKDOWN
RECOVERY_REQUIRED
```

### Increment 13.1: Canonical state model and transition table

**Status:** IN REVIEW. `SecurityState`, `VALID_TRANSITIONS`, and exhaustive
positive/negative structural tests are implemented in `domain/security.py` and
`tests/unit/test_security_state.py`. No state is persisted and no capability
behavior changes in this increment.

-   [x] Canonical state enum.
-   [x] Explicit valid transition map.
-   [x] Exhaustive valid/invalid transition tests.
-   [ ] Review and approve the structural model before persistence work.

### Increment 13.2: Versioned security-state persistence

**Status:** IN REVIEW. Migration 021 persists one constrained security-state
record with version and timestamp, seeds `NORMAL` only for a new installation,
and loads the existing record during default application startup. Missing,
invalid, or non-positive-version state raises a fail-closed error; startup does
not silently reset an existing installation to `NORMAL`.

-   [x] Singleton persisted state record.
-   [x] Version and database constraints.
-   [x] Restart loading of persisted state.
-   [x] Missing/invalid state fails closed.
-   [ ] Review and approve the persistence boundary before 13.3.

-   [ ] Exact transition rules.
-   [ ] Allowed capabilities per state.
-   [ ] Fail-closed invalid transitions.
-   [ ] Persist/audit transitions where appropriate.
-   [ ] Test each transition and denied capability.
-   [ ] Operator visibility.

**Exit gate:** Security state changes affect real capability
authorization, not merely UI labels.

## Slice 14: Backup/restore conformance

-   [ ] Backup procedure.
-   [ ] Restore procedure.
-   [ ] Automated restore fixture.
-   [ ] Deterministic before/after comparison.
-   [ ] Release checklist integration.

## Slice 15: Operator observability

Surface: - \[ \] Current cycle. - \[ \] Execution attempt/run. - \[ \]
Objective status. - \[ \] Retained evidence. - \[ \] Extracted claims. -
\[ \] Interruption/recovery reason. - \[ \] Current security state. - \[
\] Memory version/history. - \[ \] Provider attempt/budget state. - \[
\] Audit correlation/operation IDs.

## Slice 16: First live external-agent adapter

**Goal:** Add one deliberately constrained real adapter only after
internal authority and recovery mature.

-   [ ] Implement existing port rather than bypassing it.
-   [ ] No direct persistence authority.
-   [ ] No direct memory mutation authority.
-   [ ] Returned content remains untrusted data.
-   [ ] Explicit timeouts and response-size bounds.
-   [ ] Capability allowlist.
-   [ ] Retry/idempotency policy.
-   [ ] Provenance recorded.
-   [ ] Failure cannot strand cycle state.
-   [ ] Fake adapter remains for deterministic conformance tests.

# 6. Work order

``` text
NOW
 |
 +-- Slice 10A: historical authority
 |
 +-- Slice 10B: persistence invariants + CI
 |
 +-- Slice 11: execution attempts/recovery
 |
 +-- Slice 12: provider concurrency/budget
 |
 +-- Slice 13: security state machine
 |
 +-- Slice 14: backup/restore
 |
 +-- Slice 15: operator observability
 |
 +-- Slice 16: first live external-agent adapter
```

Immediate order:

1.  [x] Search/classify `assert` usage.
2.  [x] Define audit/task deletion policy.
3.  [x] Design history/version API and reconstruction service.
4.  [x] Add migration-checksum design.
5.  [x] Inventory DB-critical invariants.
6.  [x] Verify/add CI.
7.  [x] Implement Slice 10A.
8.  [x] Implement Slice 10B.
9.  [x] Re-review before Slice 11.

# 7. Regression invariants

## Authority

-   [ ] External agents cannot directly mutate governed memory.
-   [ ] Provider/model output remains untrusted until validated.
-   [ ] Operator-only actions remain operator-only.
-   [ ] Reversal rules cannot be bypassed through alternate service
    paths.

## Evidence

-   [ ] Evidence retains provenance.
-   [ ] Later failures do not silently erase retained evidence.
-   [ ] Cross-investigation evidence links are rejected.
-   [ ] Duplicate/retry behaviour is deterministic.

## Memory

-   [ ] Every governed change has an attributable journal entry.
-   [ ] Versions increase deterministically.
-   [ ] Historical state is reconstructable.
-   [ ] Current state matches latest accepted journal state.
-   [ ] Reversal never silently overwrites newer state.

## Execution

-   [ ] Paused/stopped investigations cannot be silently continued by
    stale workers.
-   [ ] Manual terminal outcomes are not overwritten by automated
    recovery.
-   [ ] Crash recovery does not duplicate evidence/claims.
-   [ ] External calls do not hold long-lived DB locks unnecessarily.

## Security

-   [ ] Capabilities are deny-by-default.
-   [ ] Untrusted content is bounded and treated as data.
-   [ ] Credentials remain ephemeral unless explicit governed storage is
    introduced.
-   [ ] Secrets never appear in audit events or ordinary logs.

## Persistence

-   [ ] Historical records are not silently destroyed by ordinary
    lifecycle operations.
-   [ ] Applied migrations are immutable.
-   [ ] Critical DB invariants survive application-layer bypass.
-   [ ] Backup/restore reproduces governed state.

# 8. Definition of Done for each slice

-   [ ] `ruff` passes.
-   [ ] `mypy --strict` passes.
-   [ ] Unit tests pass.
-   [ ] PostgreSQL integration tests pass.
-   [ ] New negative tests exist.
-   [ ] Concurrency tests exist where shared state is involved.
-   [ ] Migration from clean DB passes.
-   [ ] Existing DB upgrade path passes.
-   [ ] Smoke test passes.
-   [ ] Prototype/conformance verification passes.
-   [ ] README/API docs updated where behaviour changed.
-   [ ] This source-of-truth file updated.
-   [ ] No known P0/P1 regression is accepted merely to finish the
    slice.

# 9. Decision log

  -------------------------------------------------------------------------------
  Date              Decision              Reason                Status
  ----------------- --------------------- --------------------- -----------------
  2026-09-14        Preserve adapters -\> Prevent external      ACTIVE
                    ports -\> application systems acquiring     
                    -\>                   authority through     
                    governance/security   convenience paths     
                    -\> persistence                             
                    direction                                   

  2026-09-14        Do not rush live      Internal recovery,    ACTIVE
                    agent networking      persistence and       
                                          authority guarantees  
                                          should mature first   

  2026-09-14        Treat memory journal  Avoid redundant       PROVISIONAL
                    as candidate          competing history     
                    canonical historical  mechanisms            
                    authority                                   

  2026-09-14        Preserve committed    Provenance/recovery   PROVISIONAL
                    intermediate evidence value outweighs       
                    across later cycle    pretending the        
                    failure               workflow is one       
                                          transaction           

  2026-09-14        Prefer logical        Historical            PROVISIONAL
                    lifecycle operations  explainability is a   
                    over ordinary task    core guarantee        
                    deletion                                    
  -------------------------------------------------------------------------------

# 10. Newly discovered issue protocol

1.  Reproduce or establish the issue with evidence.
2.  Assign P0-P3.
3.  Add it to the gap register before a substantial fix.
4.  State the violated invariant.
5.  Add a regression test that fails before the fix where practical.
6.  Implement the smallest fix restoring the invariant.
7.  Check whether it reveals a broader architectural bug class.
8.  Update the decision log if architecture changed.
9.  Run the full relevant verification suite.
10. Only then mark the gap closed.

Periodically move closed implementation detail to a changelog/archive
while retaining important decisions and regression invariants.

# 11. Deferred work

Until the hardening sequence is complete:

-   multiple live agent networks;
-   broad provider expansion;
-   sophisticated autonomous planning;
-   unrelated large UI redesigns;
-   performance optimization without profiling evidence;
-   migration downgrade support unless deployment requires it;
-   broad plugin/capability ecosystems;
-   additional persistence backends.

Promote deferred work only when it removes a blocker or materially
reduces risk.

# 12. Next review gate

Perform another architecture/deep-code review after **Slice 12**.

The review must answer:

1.  Can every governed state transition be reconstructed?
2.  Can direct SQL violate an important guarantee?
3.  Can historical evidence/audit be destroyed accidentally?
4.  Can migration drift occur silently?
5.  Does CI enforce the claimed Python quality gates?
6.  Have new transaction/concurrency hazards appeared?
7.  Are cycle attempts and provider attempts modeled as distinct,
    recoverable records?
8.  Are older known-gap documents stale and ready to archive/update?

Only after this review should Slice 13 become the active development
baseline.
