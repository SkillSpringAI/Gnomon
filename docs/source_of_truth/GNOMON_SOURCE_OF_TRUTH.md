# Gnomon Hardening and Development Source of Truth

**Repository:** `SkillSpringAI/Gnomon`\
**Baseline reviewed:** `main`, 14 September 2026\
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

## GAP-001: Audit retention semantics

**Priority:** P0/P1\
**Status:** OPEN

**Problem:** Historical records have inconsistent persistence semantics.
Public research events can be coupled to task deletion through cascading
foreign-key behaviour, while the memory journal has different retention
behaviour.

**Invariant:** Deleting or archiving operational state must not silently
destroy authoritative history.

-   [x] Define canonical task lifecycle using archive/logical deletion
    instead of ordinary physical deletion.
-   [x] Review every FK from historical/audit tables for `ON DELETE`
    behaviour.
-   [x] Prevent accidental deletion of tasks owning retained history.
-   [x] Define whether historical records may ever be physically purged.
-   [ ] Require an explicit governed and audited administrative
    operation for any supported purge.
-   [ ] Align `research_events` and `memory_changes` retention semantics
    deliberately.
-   [ ] Add direct-database retention tests.

**Acceptance** - \[ \] Archive/logically delete a task and verify events
remain. - \[ \] Physical deletion is rejected or follows an explicitly
documented retention policy. - \[ \] Memory history remains attributable
to the investigation.

## GAP-002: Historical epistemic-state reconstruction

**Priority:** P0/P1\
**Status:** OPEN

**Problem:** The memory journal records previous/proposed/resulting
state and versions, but historical state is not yet a first-class
queryable capability.

**Invariant:** For every governed mutation, Gnomon can explain what
state existed, what changed, why, who/what requested it, and the
resulting state.

-   [ ] Define `MemoryChangeRecord` as the canonical historical journal.
-   [ ] Keep live claim/assessment tables as current-state projections.
-   [ ] Implement history retrieval by target.
-   [ ] Implement reconstruction/retrieval by version.
-   [ ] Verify create/update/archive/logical-delete/restore/reverse
    histories.
-   [ ] Reconstruct historical provenance links.
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
**Status:** OPEN

**Invariant:** Conditions protecting persisted or governed state use
executable validation, not `assert`.

-   [ ] Search `src/` for `assert`.
-   [ ] Classify each as programmer-only, domain, persistence, or
    external-input validation.
-   [ ] Replace domain/persistence/input assertions with explicit typed
    exceptions.
-   [ ] Keep assertions only where their removal cannot alter authority
    or persisted correctness.
-   [ ] Add negative tests.

Prefer:

``` python
if record is None:
    raise MemoryConflict("Expected governed record was not created")
```

over `assert record is not None` when correctness depends on it.

## GAP-004: Concurrent provider/report budget race

**Priority:** P1\
**Status:** OPEN

**Invariant:** Provider budget authorization and reservation are atomic.
Concurrent requests cannot collectively exceed the configured limit.

Proposed attempt states:

``` text
PENDING
SUCCEEDED
FAILED
EXPIRED
```

-   [ ] Define persistent generation attempt/reservation.
-   [ ] Add operation/request ID.
-   [ ] Atomically authorize and reserve capacity.
-   [ ] Perform remote call outside the reservation transaction.
-   [ ] Define failure/refund and timeout/expiry semantics.
-   [ ] Make retries idempotent.
-   [ ] Audit attempted/rejected/failed/successful calls distinctly.
-   [ ] Add simultaneous-request integration tests.

**Acceptance** - \[ \] Two requests competing for one remaining slot
authorize exactly one. - \[ \] Failed calls follow documented budget
semantics. - \[ \] Same operation ID cannot double-consume budget. - \[
\] Expired pending attempts recover safely.

## GAP-005: Cycle execution is becoming an implicit state machine

**Priority:** P1\
**Status:** OPEN

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

-   [ ] Introduce persistent cycle execution/run ID.
-   [ ] Define minimum useful persisted stages.
-   [ ] Link evidence, claims and outcomes to the attempt where useful.
-   [ ] Define restart/recovery semantics per stage.
-   [ ] Prevent recovered processes duplicating committed evidence.
-   [ ] Preserve manual operator outcomes over automated recovery.

**Interruption tests** - \[ \] Before discovery. - \[ \] During adapter
work. - \[ \] After observation before evidence persistence. - \[ \]
After evidence commit. - \[ \] After claim extraction. - \[ \] Before
final outcome commit.

## GAP-006: Workflow atomicity must remain explicit

**Priority:** P1/P2\
**Status:** OPEN, documentation/test hardening

**Invariant:** Successfully persisted evidence is not discarded merely
because a later cycle phase fails.

-   [ ] Document transaction boundaries.
-   [ ] Document why network/provider work must not hold long DB locks.
-   [ ] Document which intermediate artifacts survive failure.
-   [ ] Add regression tests preventing a future giant-transaction
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
**Status:** OPEN

**Invariant:** An applied migration version identifies immutable
migration content.

-   [x] Add SHA-256 checksum to migration tracking.
-   [x] Calculate checksum before application.
-   [x] Store version + checksum + applied timestamp.
-   [x] Compare applied checksum with current migration file.
-   [x] Fail closed on mismatch.
-   [ ] Test modified historical migration.
-   [ ] Document: never edit an applied migration; add a new one.

**Acceptance** - \[ \] Clean DB applies all migrations. - \[ \] Second
run is idempotent. - \[ \] Modified applied migration is rejected. - \[
\] Concurrent migration runners remain serialized.

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
**Status:** VERIFY / IMPLEMENT IF ABSENT

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
-   [ ] Split slower full-integration checks only if PR latency becomes
    excessive.

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

**Status:** COMPLETE (14 September 2026). Migration 012 adds journal version
and operation checks, migration tracking records SHA-256 checksums and rejects
drift, migration 014 adds the governed archive state, direct SQL tests cover
invalid journal writes and retained-audit deletion, and CI runs the required
quality/integration gates. No production physical-purge operation is supported;
fixture purging is explicit and test-scoped.

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

-   [ ] Cycle run/attempt identity.
-   [ ] Minimal persisted execution stages.
-   [ ] Restart/recovery policy.
-   [ ] Interruption test matrix.
-   [ ] Idempotent recovery.
-   [ ] Operator-visible recovery reason.

**Exit gate:** Every simulated crash safely resumes, safely terminates,
or explicitly requires operator recovery without silent
duplication/loss.

## Slice 12: Provider budget and concurrency governance

**Goal:** Make remote-provider use deterministic under
concurrency/retries.

-   [ ] Atomic reservation.
-   [ ] Generation attempt state.
-   [ ] Idempotency key/operation ID.
-   [ ] Timeout/expiry handling.
-   [ ] Retry semantics.
-   [ ] Concurrent integration tests.
-   [ ] Provider adapter parity tests.

**Exit gate:** Concurrency cannot bypass configured provider limits.

## Slice 13: Security state machine

**Goal:** Implement explicit operational security states.

Candidate states:

``` text
NORMAL
DEGRADED
ISOLATED
SAFE
RECOVERY
```

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
2.  [ ] Define audit/task deletion policy.
3.  [x] Design history/version API and reconstruction service.
4.  [ ] Add migration-checksum design.
5.  [ ] Inventory DB-critical invariants.
6.  [ ] Verify/add CI.
7.  [ ] Implement Slice 10A.
8.  [ ] Implement Slice 10B.
9.  [ ] Re-review before Slice 11.

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

Perform another architecture/deep-code review after **Slices 10A and
10B**.

The review must answer:

1.  Can every governed state transition be reconstructed?
2.  Can direct SQL violate an important guarantee?
3.  Can historical evidence/audit be destroyed accidentally?
4.  Can migration drift occur silently?
5.  Does CI enforce the claimed Python quality gates?
6.  Have new transaction/concurrency hazards appeared?
7.  Is `AgentCycleRunner` ready to evolve into persistent execution
    attempts?
8.  Are older known-gap documents stale and ready to archive/update?

Only after this review should Slice 11 become the active development
baseline.
