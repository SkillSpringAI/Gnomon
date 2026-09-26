# Gnomon Dependency-Ordered Development Roadmap

> Historical roadmap dated 23 September 2026, superseded by the maintained [roadmap](../../development/roadmap.md). Its implementation instructions and baseline claims are retained for provenance, not current planning authority.

> Reconciled note: this planning text has been incorporated into the maintained
> roadmap at [roadmap.md](../../development/roadmap.md). Keep repository links pointed at
> `docs/development/roadmap.md` so there is one active roadmap path. This file is
> retained as the original dependency-ordered planning snapshot.

**Baseline:** `main` at `11c46aedc3010874493fa74537b3a2ed8c64869c`
**Roadmap date:** 23 September 2026
**Purpose:** Provide a stable implementation sequence that can be followed without daily repository-wide reprioritization.

## 1. Roadmap Rule

Gnomon development follows dependency order rather than opportunistic feature selection.

Work moves to the next milestone only when the current milestone's exit gate is satisfied.

Do not perform a new repository-wide priority review after every completed slice.

Re-open roadmap ordering only when one of these occurs:

1. a security or authority invariant is shown to be unsound;
2. a milestone dependency proves incorrect;
3. hosted CI exposes a previously unknown systemic failure;
4. implementation evidence contradicts canonical documentation;
5. a requirement changes the intended v0.1 boundary;
6. a discovered defect makes later roadmap work unsafe.

Ordinary implementation friction does not trigger roadmap redesign.

---

# Milestone 0: Restore a Green Canonical Baseline

## Objective

Establish one exact commit that is locally and hosted verified before further architectural work.

## Current blocker

Quality run `35818573020` for `11c46ae` failed during the ordinary pytest job.

Observed result:

- Ruff: passed
- strict mypy: passed
- migrations: passed
- browser job: passed
- minimal wheel install: passed
- pytest: 1,647 passed, 24 skipped, 2 setup errors
- failures originate from missing `dependence_context` fixture in `test_source_dependence_listing.py`

This appears to be test-suite/fixture integration rather than evidence that the source-dependence runtime itself failed, but the canonical HEAD is not green until corrected and rerun.

## Work

### M0.1 Test fixture closure

Repair the source-dependence listing test fixture boundary.

Verify that the tests:

- use the intended shared fixture;
- run when invoked alone;
- run as part of the full test suite;
- do not depend accidentally on import or collection order.

### M0.2 Full verification

Run:

- Ruff
- strict mypy
- normal pytest
- PostgreSQL integration
- migrations
- smoke verification
- prototype verification
- conformance check
- wheel verification
- hosted browser suite

### Exit gate

Milestone 0 closes only when one implementation SHA has a successful hosted Quality run across all required jobs.

Do not begin architectural expansion from a known-red HEAD.

---

# Milestone 1: Recovery Authority Completion

## Objective

Finish the authority model required to recover Gnomon itself safely.

This is the highest-priority architectural milestone.

Gnomon already knows how to enter restrictive recovery bootstrap. It does not yet have a complete governed path back out.

## 1.1 Canonical RecoveryContext

Define an immutable/bounded recovery context containing at minimum:

- current authority epoch;
- security-state identity and version;
- recovery-bootstrap origin state/version;
- incident/recovery identifier;
- initiating actor;
- permitted recovery scope;
- evidence basis;
- required reconciliation items;
- unresolved/unknown operations;
- creation time;
- validity/expiry rules where applicable.

RecoveryContext is evidence about a recovery operation.

It is not authority by itself.

## 1.2 OperatorAuthorization

Separate operator identity from operator authority.

Define a structured authorization artifact containing:

- authenticated principal or current bounded local identity;
- granted capability;
- scope;
- authority epoch;
- issuance basis;
- expiry;
- replay/idempotency identity;
- optional recovery-context binding.

Do not allow possession of a RecoveryContext to imply permission.

## 1.3 ExecutionAuthorization epoch binding

Any authority-bearing execution authorization must be bound to the authority epoch under which it was issued.

An authorization from a superseded epoch must fail closed.

## 1.4 Recovery reconciliation

Implement deterministic reconciliation of recovery-bootstrap state.

The service should determine, without model discretion:

- what authoritative state survived;
- which operations definitely committed;
- which definitely did not;
- which remain unknown;
- which provider/network attempts require reconciliation;
- whether retained evidence is structurally valid;
- whether audit/history chains remain valid;
- whether restoration is allowed to proceed.

Reads must not silently repair state.

## 1.5 Protected authority restoration

Implement explicit recovery transitions rather than treating recovery as administrative superuser mode.

Restoration must require:

- valid current authority;
- RecoveryContext;
- appropriate OperatorAuthorization;
- successful required reconciliation;
- expected security-state version;
- valid authority epoch;
- structured reason code;
- atomic audit.

Direct `LOCKDOWN -> NORMAL` remains prohibited.

## 1.6 Authority epoch replacement

Define the conditions under which a new authority epoch is created.

The old epoch remains historical evidence.

New authority must not rewrite previous attribution.

Explicitly specify behavior for:

- old outstanding execution authorizations;
- unknown provider attempts;
- stale operator commands;
- recovery records;
- audit projections;
- restored database state.

## Required adversarial tests

Include at minimum:

- stale RecoveryContext;
- stale authority epoch;
- stale OperatorAuthorization;
- duplicated recovery command;
- concurrent restoration requests;
- recovery interrupted midway;
- audit failure;
- invalid persisted authority state;
- unknown provider outcome;
- restrictive transition racing restoration;
- replay of authorization from old epoch;
- model/external-agent attempt to manufacture recovery authority.

## Exit gate

Milestone 1 closes when Gnomon can enter restrictive recovery, reconcile its authoritative state, perform a separately authorized restoration, establish the correct authority epoch and preserve an auditable history without granting recovery implicit superuser semantics.

---

# Milestone 2: Backup, Restore and Reconstruction Conformance

## Objective

Prove that authoritative Gnomon state survives infrastructure loss.

Backup/restore follows recovery authority rather than preceding it.

## 2.1 Supported backup procedure

Define one canonical PostgreSQL backup procedure.

Specify:

- database scope;
- supported PostgreSQL version;
- expected migration state;
- credential exclusion;
- operator requirements;
- consistency expectations.

## 2.2 Restore fixture

Create a populated fixture containing:

- investigation state;
- evidence;
- claims;
- provenance;
- assessments;
- source relationships and history;
- stopping decisions and command journals;
- cycle attempts;
- provider attempts;
- memory history;
- audit records;
- restrictive security state;
- authority epoch data.

## 2.3 Restoration verification

After restore, compare:

- authoritative records;
- versions;
- append-only histories;
- provenance;
- audit history;
- security state;
- authority epoch;
- command identities;
- deterministic snapshots/reports.

## 2.4 Restore into recovery, not blind continuation

A reconstructed deployment must not simply assume that restored authority is safe to resume.

Bind restoration to the Milestone 1 recovery model.

Determine whether:

- the same epoch can continue;
- a new epoch is required;
- outstanding external operations remain unknown;
- old execution authorization must be invalidated.

## 2.5 Credential non-persistence verification

Prove that database backup does not inadvertently become a credential archive.

Provider/API credentials must not appear in:

- research state;
- audit;
- recovery context;
- reports;
- command journals;
- backup fixtures.

## Exit gate

A destroyed test deployment can be rebuilt from the supported backup and deterministically reach a valid governed state through the recovery path.

Only after this milestone should the project claim meaningful backup/restore readiness.

---

# Milestone 3: Runtime and Persistence Hardening

## Objective

Reduce remaining infrastructure ambiguity before introducing live autonomous networks.

## 3.1 Runtime/database role separation

Separate migration authority from normal runtime database authority.

The normal application role should not possess schema-management privileges merely because migrations require them.

## 3.2 Constraint coverage review

Review remaining authoritative vocabularies and state machines for database-level enforcement where appropriate.

Candidates include:

- cycle lifecycle vocabulary;
- provider outcome vocabulary;
- remaining memory-history categories;
- authority-bearing command fields.

Do not mirror every application validation blindly in SQL.

Add database constraints where corruption below the application layer would violate an important invariant.

## 3.3 Persistence failure taxonomy

Extend structured persistence diagnostics beyond the currently reviewed constraint paths.

Maintain the distinction between:

- known conflict;
- rejected invariant;
- transient database failure;
- unavailable persistence;
- ambiguous commit;
- unexpected persistence defect.

## 3.4 Ambiguous commit testing

Introduce explicit connection-loss/ambiguous-commit tests.

Do not treat transaction rollback tests as proof of ambiguous commit recovery.

Verify idempotency/reconciliation around operations where the caller may not know whether PostgreSQL committed.

## 3.5 Audit durability boundary

Decide and document the durability promise Gnomon actually makes.

If privileged-operator tamper evidence is required for the target release, design cryptographic history protection here.

If it is not required, retain append-only application semantics without overstating tamper resistance.

## Exit gate

Database privileges, failure semantics and authoritative invariants support the recovery guarantees established in Milestones 1–2.

---

# Milestone 4: Architectural Consolidation

## Objective

Prevent the hardened prototype from becoming increasingly expensive to change.

This milestone is not a rewrite.

Refactor only around proven responsibilities.

## Current concentration points

Review especially:

- `source_dependence_service.py`
- `memory_service.py`
- `stopping_decision_service.py`
- `research_service.py`
- `persistence/models.py`
- `workspace.html`

File size alone is not a defect.

Refactoring is warranted where multiple independent authority responsibilities, transaction boundaries or policy decisions are becoming inseparable.

## 4.1 Source dependence seams

Potential separation:

- command/replay handling;
- relationship mutation;
- graph validation/traversal;
- history projection;
- review invalidation.

Preserve one authoritative transaction owner for writes.

## 4.2 Stopping decision seams

Separate where useful:

- command acceptance/replay;
- readiness calculation;
- objective reference resolution;
- limitation derivation;
- persistence orchestration.

The deterministic stopping verdict remains application authority.

## 4.3 Memory governance seams

Separate:

- proposal validation;
- acceptance;
- history/versioning;
- reversal authorization;
- dependent-state invalidation/reassessment.

Do not weaken the existing atomic mutation/audit guarantees during extraction.

## 4.4 Persistence model organization

Consider splitting model declarations by bounded domain while retaining one metadata/migration authority.

Avoid creating repository abstractions solely for aesthetic symmetry.

## 4.5 Workspace boundary

The current workspace may remain a single deployable operator surface, but separate presentation assets/components enough that new controls do not continually expand one monolithic HTML file.

The workspace remains a client of application/API authority.

It must never become the place where security or research policy is decided.

## Exit gate

Critical services expose clear internal responsibilities and future work can be added without modifying unrelated authority paths.

All behavior remains equivalent under the existing conformance suite.

---

# Milestone 5: Unified Bounded Execution Envelope

## Objective

Generalize the successful source/agent/provider attempt patterns before connecting live external agents.

Do not create a general autonomous agent framework yet.

First define a common bounded execution contract.

## Required concepts

A bounded execution should possess:

- execution ID;
- task/cycle scope;
- authority epoch;
- explicit capability grants;
- budget;
- deadline;
- attempt identity;
- security-state guard;
- cancellation/interruption semantics;
- audit identity;
- result classification;
- unknown-outcome semantics;
- reconciliation requirements.

## Budget hierarchy

Support explicit parent/child bounds for:

- model calls;
- network requests;
- external-agent requests;
- bytes retrieved;
- tool calls;
- elapsed execution time;
- retries;
- memory mutations.

A child execution cannot silently exceed its parent authority or budget.

## Exit gate

Source retrieval, provider execution and fake-agent execution can all be explained through one bounded runtime contract without erasing their domain-specific semantics.

---

# Milestone 6: Fresh-Agent Handoff Architecture

## Objective

Introduce secure chain-of-agent semantics before introducing arbitrary live agent continuity.

Each agent execution should begin from a freshly constructed context rather than inheriting another agent's raw working context.

## 6.1 Structured handoff artifact

Define a bounded handoff object containing only information intentionally transmitted to the next agent.

Potential fields:

- handoff ID;
- source execution/agent identity;
- destination role;
- task/cycle identity;
- authority epoch;
- objective;
- accepted evidence references;
- accepted claim references;
- unresolved questions;
- declared limitations;
- previous outcome;
- permitted capabilities;
- remaining budget;
- provenance;
- integrity metadata.

## 6.2 Fresh execution context

The receiving agent starts from:

- trusted system/runtime policy;
- current Gnomon state;
- explicitly approved task instructions;
- validated structured handoff.

It does not inherit:

- previous hidden reasoning;
- arbitrary raw prompt history;
- unvalidated external instructions;
- previous agent credentials;
- previous agent authority merely because it appeared in the handoff;
- tool outputs as executable instructions.

## 6.3 Handoff validation

Treat handoffs as proposals/data until application validation succeeds.

Validate:

- task scope;
- authority epoch;
- source execution;
- accepted evidence identity;
- capability scope;
- budget;
- freshness;
- integrity.

No agent may grant the next agent more authority than it possessed.

## 6.4 Prompt-injection containment tests

Test handoffs containing:

- instructions embedded in retrieved evidence;
- fake administrator messages;
- fabricated capability grants;
- requests to expose credentials;
- attempts to expand task scope;
- attempts to override stopping decisions;
- stale authority-epoch references;
- malicious previous-agent summaries.

## Exit gate

Multi-agent chaining can occur without requiring agents to trust raw inherited context.

Agent continuity exists at the level of governed state and explicit handoff artifacts, not uncontrolled conversational continuity.

---

# Milestone 7: First Real External-Agent Adapter

## Objective

Connect exactly one real external-agent platform through the established boundary.

Do not begin with a generalized multi-platform plugin framework.

## Work

Implement one adapter supporting:

- bounded agent discovery/selection;
- request dispatch;
- response ingestion;
- timeout;
- retries where safe;
- durable attempt identity;
- unknown outcomes;
- structured handoff support;
- provenance;
- security-state cancellation/fencing;
- capability enforcement;
- redacted audit.

External-agent output remains observation/proposal data.

It cannot:

- mutate authority;
- modify capability policy;
- accept memory proposals directly;
- alter stopping state directly;
- register trusted sources;
- restore security state.

## Exit gate

One live adapter passes the same bounded execution, prompt-injection, recovery, provenance and interruption invariants already established locally.

Only then consider a second agent platform.

---

# Milestone 8: Long-Running Worker Orchestration

## Objective

Move from request-bound execution to durable asynchronous research execution.

Introduce only after attempts, recovery, authority and external boundaries are mature.

## Work

Design:

- durable work queue;
- leased execution;
- worker identity;
- heartbeat/expiry;
- restart recovery;
- cancellation;
- per-task serialization where required;
- distributed idempotency;
- provider/network attempt reconciliation;
- security-state propagation;
- bounded concurrency.

A worker crash must not manufacture a success or silently retry an unknown external side effect.

## Exit gate

A research cycle can survive process termination and continue or require explicit reconciliation from persisted authoritative execution state.

---

# Milestone 9: Epistemic Expansion

## Objective

Improve research intelligence only after runtime authority is dependable.

Candidate work:

### 9.1 Dependency-aware reassessment

When an accepted claim changes or is reversed:

- identify dependent assessments;
- mark affected conclusions stale where justified;
- preserve previous history;
- require deterministic or governed reassessment.

### 9.2 Richer source dependence

Potential later capabilities:

- automatic duplicate/common-origin suggestions;
- bounded transitive analysis;
- source-family grouping;
- causal relationship proposals.

Automatic inference remains a proposal until accepted under application policy.

### 9.3 Semantic retrieval

Add semantic/vector retrieval only as an index over canonical structured state.

Vector similarity must never become the source of record for:

- authority;
- provenance;
- security state;
- mutation history;
- accepted claims.

### 9.4 Additional source formats

Add PDF, structured documents or other extractors where there is a concrete research need and bounded parsing model.

---

# Milestone 10: v0.1 Release Candidate

## Required claims

A v0.1 candidate should be able to demonstrate:

- deterministic authority boundaries;
- persisted investigation/evidence state;
- bounded research execution;
- provenance and uncertainty preservation;
- governed memory mutation;
- explicit stopping decisions;
- source-dependence handling;
- durable attempt/recovery semantics;
- canonical security state;
- governed recovery and restoration;
- tested backup/restore;
- replaceable provider/network adapters;
- hosted reproducible verification.

## Release gate

Before tagging v0.1:

1. canonical HEAD is green;
2. all database migrations succeed from a fresh database;
3. supported populated upgrade paths succeed;
4. backup/restore drill succeeds;
5. recovery drill succeeds;
6. stale authority and stale epoch tests pass;
7. restrictive security-state tests pass;
8. browser/operator workflow passes;
9. package/wheel verification passes;
10. canonical documentation agrees with runtime behavior;
11. no P0 issue remains open;
12. remaining P1/P2 limitations are explicitly documented;
13. external credentials are absent from persistent research/audit state;
14. an adversarial security/conformance pass is recorded.

---

# Deferred Beyond v0.1 Unless Pulled Forward by Evidence

Do not let these interrupt the critical path without a concrete requirement:

- multiple live agent platforms;
- broad plugin/tool registry;
- general shell or arbitrary-code tool;
- distributed deployment;
- multi-tenant authentication;
- high-volume graph optimization;
- automatic semantic stopping;
- cross-investigation semantic memory;
- advanced UI redesign;
- broad source discovery;
- generalized causal inference;
- cryptographic audit anchoring unless required by the release threat model;
- mobile/tablet clients.

---

# Working Cadence

Use this roadmap at three levels.

## Milestone

A milestone represents a dependency boundary and should remain stable.

## Slice

Each implementation session selects one bounded slice from the current milestone only.

A good slice should normally:

- change one authority concept or one coherent runtime behavior;
- define negative behavior as well as success behavior;
- include its tests;
- avoid pre-implementing later milestones.

## Closure

A slice closes only when:

1. implementation is committed;
2. focused tests pass;
3. required full-suite verification passes;
4. hosted CI passes where required;
5. canonical docs are updated;
6. remaining limitations are recorded without immediately turning all of them into new work.

---

# Roadmap Review Cadence

Do not conduct a fresh deep priority review every day.

Perform roadmap review:

- at milestone closure;
- when one of the explicit roadmap-reopening triggers occurs;
- before a tagged release candidate.

During normal development, ask only:

> What is the next unfinished dependency inside the current milestone?

That question replaces recurring repository-wide reprioritization.
