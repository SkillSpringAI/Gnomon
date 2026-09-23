# Gnomon: priority slices for 22 September 2026

Status: execution proposal from repository review; no implementation performed in this review.
Reviewed HEAD: `35550b80d14e2ab4f0ca31208451ca8d255ba544`.
Predecessors: `2026-09-21-next-three-priority-steps.md` and `2026-09-21-step-2-contract-decisions.md` in this directory.

## Today's direction

Complete the new research workflow before opening another major capability. Source-dependence and stopping-decision APIs now exist, but contract edge cases and operator interaction remain incomplete. Today's three slices are:

1. Close source-dependence replay, history and bounded-read correctness.
2. Close stopping-decision replay and evidence/readiness correctness.
3. Make both capabilities usable through the workspace, with real browser acceptance coverage.

This moves the project toward a usable, evidence-driven research loop. Do not restart the completed provider-session work or introduce autonomous execution to bypass unfinished operator controls.

## Latest commit review

| Commit | What changed | Review conclusion |
|---|---|---|
| `b22d2e8` | Source relationships, migration 028, dedicated current/history tables, contract API and report/planner/workspace projections | Canonical storage decisions were implemented. Closure is narrower than the predecessor's full negative-test matrix. |
| `79e7c81` | Source-dependence documentation closure | Useful baseline evidence; not proof of every previously proposed edge-case contract. |
| `ca08943` | Provider-session rollback/concurrency work, populated memory upgrade coverage, stopping decisions and migration 029 | Previous provider/upgrade gaps are addressed in the bounded implementation. Preserve documented crash-ambiguity limits. New stopping behavior needs the corrections below. |
| `35550b8` | Provider/stopping closure evidence | Current clean HEAD; hosted Quality also passed for this documentation commit. |

Hosted results queried during this review:

- [Source-dependence implementation run 35554268153](https://github.com/SkillSpringAI/Gnomon/actions/runs/35554268153): success for `b22d2e83075bf22e2f73e39572ce662e0b8272b9`.
- [Provider/stopping implementation run 35558052346](https://github.com/SkillSpringAI/Gnomon/actions/runs/35558052346): success for `ca08943cf8baf3d8fb9d2d8d01dfb6c01cbe30e5`.
- [Current HEAD run 35558385008](https://github.com/SkillSpringAI/Gnomon/actions/runs/35558385008): success for `35550b80d14e2ab4f0ca31208451ca8d255ba544`.

The existing browser suite still has five cases centered on source collection, objective selection/review and interruption recovery. Neither implementation commit adds browser tests for relationship editing or stopping submission. The workspace additions display summary paragraphs; they do not provide those operator workflows. A successful existing browser job cannot close the predecessor's new browser acceptance requirements.

## Findings that drive the sequence

### Source-dependence contract gaps — code-inspected

`SourceDependenceService._retry_or_conflict()` compares selected resulting-state fields, but not the full accepted command, reason, actor, expected revision or reversal target. It returns the current projection rather than the historical result associated with the accepted operation. A retry after later corrections can therefore return a different revision. The mutation retry branch also resolves omitted fields against current state; its omitted SET lifecycle expression differs from the normal SET default. These require command-level regression tests, not more happy-path retries.

`history()` serializes rows without checking contiguous revisions, previous/resulting continuity or agreement with the current head. Migration 028 has several useful identity and ownership constraints but does not establish the predecessor's complete history-integrity contract. “Immutable history” must be scoped to actual supported write/role guarantees, not inferred from append-oriented code.

`project()` does not visibly establish a stable database snapshot across adjacency queries. `SnapshotService` copies every omitted source ID into `frontier_source_ids` when more than 100 roots exist, defeating a bounded frontier payload. Invalid persisted directional graphs are listed as deferred recovery, but detection and honest read limitations are separate from recovery and should not be deferred together. Existing tests cover depth overflow but do not establish all 100-node/500-edge boundaries or reciprocal concurrent writes.

### Stopping contract gaps — one reproduced, others code-inspected

`decide()` combines caller limitations with server-generated readiness limitations. `_retry_or_conflict()` compares stored combined limitations against only the caller's list. An isolated synthetic helper probe reproduced a conflict for an otherwise identical retry with an originally empty limitations list after a server-added limitation. No database or user data was touched by the probe. Add a full API regression for this scenario.

The decision builder takes only the first 20 combined limitations after placing caller text first; 20 caller entries can crowd out every derived limitation. `_validate_references()` indexes the last cycle when objective indices are provided without first proving a cycle exists. Readiness considers only the latest cycle's unresolved list and contested/contradicted claim status, potentially diverging from report/planner logic for prior unresolved work, stale reviews and contradicting evidence links. These cases need characterization and correction before the UI presents readiness as complete.

`runtime_limit_evidence` currently accepts caller strings. They are operator assertions unless verified against durable runtime records; never describe them as measured exhaustion solely because that field is populated.

## Slice 1 — Source-dependence contract closure

**Outcome:** A relationship command has stable identity, an auditable result and bounded, honest read semantics under failure and concurrency.

Work:

1. Add failing tests for same operation/different reason, actor, command kind, revision and reversal target; exact retries after later mutations; reversed symmetric endpoint normalization; and SET with omitted optional fields. Compare a persisted canonical request representation or digest with a defined normalization/version policy. Return the originally accepted result, not today's projection. Keep current authorization checks on retries.
2. For older migration-028 history that lacks the full request, define conservative compatibility. Do not invent original command fields from a later current projection. Use a new migration if required; never edit a checksummed migration.
3. Validate historical chain and current/head consistency on the appropriate reads. Reject malformed/missing/contradictory history safely without repair. Document and test actual application/database-role protections against history edits; do not promise privileged-database tamper resistance.
4. Establish a consistent read snapshot for traversal and its consumers without breaking caller-owned transactions. Bound the frontier sample as well as roots, nodes and edges. Include an explicit indication of omitted frontier entries; do not calculate an unbounded exact total merely to decorate a partial response.
5. Detect invalid directed graphs in the examined portion and mark the result invalid/incomplete; truncated inspection cannot certify the rest. Do not implement graph repair. Keep common-origin pairwise and non-transitive.
6. Prove reciprocal-edge concurrency and both relevant mutation/lockdown orderings in PostgreSQL. Prove cycle-validation overflow rejects the write with no success state/history/audit.

Acceptance:

- Canonical identical retry produces the original accepted result and no additional event; conflicting commands never masquerade as a retry.
- Tests cover exact and exceeded node/edge/depth limits, multi-root shared budgets, deterministic output, high fan-out and bounded frontier serialization.
- Concurrent reads do not assemble a graph from incompatible committed versions. Omitted or invalid regions never yield complete/independent claims.
- History tampering/missing revision/current-head mismatch have explicit tested behavior; reading never writes.
- Report/planner fingerprints still invalidate on relevant new or changed relationships without treating unknown dependence as independent.

## Slice 2 — Evidence-bound stopping correctness

**Outcome:** An operator can retry a conclusion reliably, and accepted decisions retain all material evidence limitations.

Work:

1. Reproduce the server-added limitation retry failure through the API. Persist/compare the canonical accepted request independently from derived decision fields. Include trusted actor and command identity semantics, and return the historical accepted decision on exact retry.
2. Preserve derived limitations even when the caller supplies the maximum allowed entries. Use separately bounded caller/system fields or a clearly defined merge/truncation contract that cannot erase material system warnings. Expose any necessary truncation explicitly and retain references to the structured readiness basis.
3. Validate objective references when there are no cycles and define cycle identity for objective indices. Never leave an index whose meaning depends on an implicit mutable “last cycle.” Preserve backwards compatibility explicitly if adding a cycle identifier or structured reference.
4. Reuse or reconcile report/planner semantics for unresolved objectives, current versus stale completed reviews, missing/unresolved/mixed assessments, contradicting links and active execution. No recorded evidence is unknown/insufficient evidence, not a satisfied independence check. Keep the checklist advisory: an operator can stop with limitations, but lifecycle conclusion must not upgrade truth status.
5. Separate claimed budget/deadline exhaustion from system-verified evidence. Validate any runtime-record references; otherwise label the reason as operator-reported. Do not build a new accounting system in this slice.
6. Verify canonical fingerprint ordering and the source-dependence completeness/invalidity inputs from Slice 1. Preserve stale-basis refusal and historical decision immutability.

Acceptance:

- Identical requests with server-generated limitations retry successfully; altered actor/request identity conflicts without a second decision/event.
- Zero cycles plus objective references yields a stable client error, never an unhandled index error.
- Prior unresolved work and stale reviews remain visible; contradicted links cannot disappear merely because a claim's status has not changed.
- Maximum caller limitations cannot suppress mandatory derived limitations; partial dependence remains explicit.
- Resource-limited and evidence-sufficient reasons preserve the same underlying uncertain claims. Unsupported runtime claims remain attributed to the operator.
- Audit failure, stale basis/revision, simultaneous decisions, active execution and security-transition races leave no partial lifecycle/decision changes. Legacy direct conclusions remain explicitly unspecified.

## Slice 3 — Complete the operator research workflow in the workspace

**Outcome:** A user can record/review source dependence and make an informed stopping decision without constructing API requests manually.

Work:

1. Add a compact relationship editor using existing task sources: derived source → upstream source, or symmetric common-origin pair. Explain direction in plain language. Show current revision/history and supported retract/reversal actions without implying independent corroboration.
2. Fetch and display stopping readiness with referenced evidence and all limitations. Let the operator choose a reason, supply rationale and review the basis before submitting. Explain resource exhaustion versus evidence sufficiency in user language; do not ask the model to decide truth.
3. Submit expected state/revision/fingerprint and stable operation identity. Preserve identity for an ambiguous network retry of the same command; allocate a new identity for an intentionally changed command. Disable duplicate submissions while busy.
4. On stale/conflicting evidence, refresh the basis and preserve the user's draft for review rather than silently reapplying it. Show unresolved active-attempt and security denials clearly. Reload must reproduce accepted history and decisions.
5. Keep summaries, read-only reports and provider drafts aligned with accepted stopping limitations and partial/unknown dependence. New views render external/user text safely.
6. Extend the existing browser suite and deliberately update its exact-case enforcement. Add actual relationship and stopping interactions; a static HTML assertion is not interaction evidence. Keep bridge-based browser tests distinguished from real HTTP prototype/restart checks.

Acceptance:

- Browser cases cover relationship create/correct/retract, direction labels, stale edits and unknown/truncated views; stopping review/submit, server-added limitations, exact retry, stale evidence and reload.
- Simulated connection loss after server acceptance cannot create duplicate history on retry.
- Test empty data, long rationale, narrow viewport, hostile text and inaccessible/denied actions. No broad visual redesign is required.
- One disposable end-to-end scenario runs acquisition → relationship review → objective/assessment review → reasoned stop → reload/report, preserving uncertainty and provenance throughout.

## Execution and evidence rules

### Pass reporting rule

After every implementation or verification pass, report and record:

- findings and risks discovered during the pass;
- which acceptance or completion criteria remain blocked;
- hardening recommendations tied directly to those gaps; and
- whether the recommendation is required for closure, recommended for the next
  pass, or explicitly deferred by scope.

- Reconcile current HEAD and applicable instructions before implementation. The worktree was clean during this review; preserve any changes made afterward.
- Work in the order above and checkpoint each slice separately. The previous “keep Step 1 uncommitted” instruction concerned then-pending provider changes; those are now committed and hosted-verified. Do not undo or uncommit them.
- For each correction, establish a failing focused regression first. Use disposable databases for corruption, migrations and concurrency. No destructive verification against user data.
- At closure run applicable focused and full Quality checks, strict typing/lint, conformance, migration/packaging checks, smoke/prototype restart and required browser tests. Record exact results and skips; do not copy old counts.
- Update maintained current truth, affected authority-matrix rows and implementation status with precise supported scope. A green suite proves its tested cases, not every acceptance item from an earlier proposal.
- Capture implementation SHA and hosted run/tested SHA separately from documentation follow-ups. Keep outstanding failures as open acceptance items rather than changing the claim to “closed” with broad deferrals.
- Preserve current capability matrices, authority epochs, task/security lock order, recovery-bootstrap restrictions, evidence retention and unknown-provider-outcome semantics.
- No RecoveryContext, fence clearing, epoch replacement, protected restoration, backup tooling, autonomous scheduling, live external agents, semantic-memory expansion or broad authentication work today. These remain separate architectural milestones, not hidden dependencies to add mid-slice.
- Keep this directive local and ignored; promote lasting contracts and evidence into maintained docs. At the end of the sequence, reassess the next capability milestone using the completed operator workflow rather than automatically adding more hardening slices.

## Review boundary

This review inspected latest commits, relevant implementation/migrations/tests, prior directives, current status/roadmap and hosted run results. It ran one isolated synthetic stopping-retry probe. It did not rerun the full suite or claim an exhaustive security audit. Only this directive was created; fixes and new tests are subsequent implementation work.

## Slice 1 — pass 1 record: canonical command identity and historical retries

Implemented and locally verified the first Slice 1 pass:

- Added migration `030_source_dependence_command_requests.sql` without editing the checksummed migration 028.
- Persisted a versioned normalized command request beside each new relationship-history row.
- Replay comparison now includes command kind, normalized relationship content, reason, expected revision, reversal target where applicable, and actor identity.
- Exact retries return the accepted historical `resulting_state`, rather than re-reading the mutable current projection.
- Mutation and reversal retries check operation identity before loading the current projection, so later mutations cannot change omitted SET defaults or otherwise alter replay meaning.
- Legacy history rows with no command metadata fail conservatively instead of inventing a request from current state.
- Added regressions for later-mutation replay, changed reason/actor, omitted SET defaults, and legacy metadata absence.

Verification:

- `pytest -q tests/integration/test_source_dependence_contract.py` — 15 passed.
- `python -m ruff check src tests/integration/test_source_dependence_contract.py` — passed.
- `git diff --check` — passed.
- Local migration application — `030_source_dependence_command_requests.sql` applied successfully.

Findings and risks:

- The ORM change is migration-sensitive: an environment that starts the new code without applying migration 030 fails closed at the database schema boundary. Deployment ordering must remain “migrate, then serve.”
- Existing migration-028 rows remain replay-ineligible when their request metadata is absent. This is deliberate conservative compatibility, but it is a behavior limitation for historical operations.
- Canonical request fields are currently stored as JSON rather than a separate digest/typed table. Equality is deterministic for the service-generated dictionaries, but future command-schema changes require an explicit version migration or compatibility policy.
- History-chain integrity, current/head consistency, stable traversal snapshots, bounded frontier serialization, invalid-graph detection, and reciprocal-edge concurrency remain unverified and therefore remain open Slice 1 acceptance items.

Blocked criteria after this pass:

- Slice 1 is not closure-ready. The pass closes only canonical identity and historical-result replay coverage.
- No claim is made yet for exact/exceeded node, edge, depth, shared multi-root budgets, deterministic traversal under concurrent commits, history tamper behavior, invalid directed-graph reporting, or cycle-validation concurrency.

Recommendations:

- Closure-required: apply and verify migration 030 in every supported test/deployment path before any commit claiming Slice 1 replay closure.
- Required for the next Slice 1 pass: add history continuity/current-head validation with read-only corruption fixtures and explicit failure semantics.
- Recommended for the next Slice 1 pass: define a canonical-request schema/version compatibility test so future command additions cannot silently change replay identity.
- Deferred by scope: backfill command metadata for migration-028 rows; the current safe behavior is to reject replay when the original request cannot be proven.

## Slice 1 — pass 2 record: read-only history-chain validation

Added integrity validation to the relationship-history read:

- History and current projection are fetched by one joined SQL statement, so the compared rows share that statement's database snapshot.
- The read rejects absent history, non-contiguous revisions, invalid CREATE placement, incorrect previous-revision counters, mismatched previous/resulting states, row/state identity mismatches, and a projection that disagrees with the final history result.
- Corruption cases are tested as persisted fixtures. The tests confirm the read reports an integrity conflict and leaves the corrupt data unchanged; there is no read-time repair.

Verification:

- pytest -q tests/integration/test_source_dependence_contract.py — 19 passed.
- python -m ruff check src/research_agent/application/source_dependence_service.py tests/integration/test_source_dependence_contract.py — passed.
- git diff --check — passed.
- The focused PostgreSQL integration run used the local schema with migration 030 already applied during pass 1; migration execution itself was not repeated in this pass.

Findings and risks:

- One-statement consistency applies to this history endpoint's comparison, not yet to graph traversal or report/planner consumers.
- The validation establishes internal chain consistency and current-head agreement, not cryptographic tamper evidence or resistance to a privileged database operator rewriting all related rows coherently.
- The current corruption suite covers predecessor mismatch, revision gap, absent head row, and projection mismatch. Other malformed payload/identity combinations rely on the shared validator and still merit focused coverage.

Blocked criteria after this pass:

- Slice 1 remains open: stable snapshots across projection traversal/consumers, bounded frontier output and omitted-frontier indication, invalid directed-graph detection, complete node/edge/depth and shared-budget boundaries, reciprocal-edge concurrency, mutation/lockdown orderings, and cycle-validation overflow atomicity are not addressed here.
- Application/database-role immutability guarantees for relationship history have not been established; no stronger immutability claim is made.

Recommendations:

- Closure-required: confirm supported database privileges prevent ordinary application identities from updating/deleting relationship-history rows, or explicitly retain the narrower append-only-by-application claim if they do not.
- Required for a later Slice 1 pass: apply a consistent snapshot and shared bounded traversal budget to graph reads and their consuming projections.
- Recommended for a later pass: add malformed result-state and wrong relationship/task identity fixtures to exercise the remaining validator branches.
- Deferred by scope: cryptographic history chaining and privileged-database tamper resistance.

## Review checkpoint — recorded findings and proposed continuation

Status: review of the two recorded passes, not additional implementation or approval of scope changes.

HEAD remains `35550b8`. Current uncommitted work is limited to the source-dependence service, persistence model, contract tests and new migration 030. The pass records match those changes. No stopping-service, workspace or browser-test changes are present in this working-tree diff. Recorded results are 15 focused passes after pass 1 and 19 after pass 2, plus the stated Ruff/diff checks; this review did not independently rerun them. No full-suite, strict-mypy, packaged-upgrade or hosted verification is recorded for this uncommitted tree.

### Recommendation and finding reconciliation

| Item | Recorded and code-supported status | Proposed disposition |
|---|---|---|
| Full canonical command identity and historical retry result | Implemented locally; versioned JSON command metadata, actor comparison and historical result return are present. Four new replay-focused tests are visible. | Provisionally addressed; complete the negative matrix and closure checks before calling it closed. |
| Legacy operations without original command metadata | Explicit conservative rejection recorded and implemented through nullable migration 030. | Accept this bounded compatibility rule; defer backfill rather than inventing old commands. |
| Canonical command schema/version evolution | Versioned service-generated representation exists; a compatibility test remains a recommendation. | Add focused unknown-version and changed-schema behavior before replay closure. |
| History continuity and current/head agreement | One joined statement plus validation and four corruption tests are present. | Provisionally addressed for tested cases; add malformed-state and wrong-identity cases before history closure. |
| Graph/read snapshot consistency | Explicitly still open; the history endpoint's single-statement fix does not fix traversal. | Required next; cannot defer while claiming consistent graph projections. |
| Bounded frontier and exact traversal budgets | Explicitly still open; no consumer/frontier changes in this diff. | Required next, including exactly-at-limit and one-over-limit behavior. |
| Invalid persisted directed-graph detection | Still open. | Required for honest examined-graph results; repair remains separate. |
| Reciprocal edge concurrency, lockdown ordering and overflow atomicity | Still open; dedicated proof not added in these passes. | Required before Slice 1 closure. |
| Ordinary database-role history protections | Explicitly unestablished. | Inspect actual supported grants/ownership read-only and record the guarantee. Do not infer protection from the validator. |
| Stopping retry, limitation loss, objective references, readiness and runtime attribution | Recorded in the original directive; not addressed by these passes. | Required Slice 2 work before exposing the new conclusion flow. |
| Workspace editing/stopping workflows and browser coverage | Recorded; not addressed by these passes. | Slice 3 after backend closure. Existing summary rendering is not workflow completion. |
| Migration/deployment ordering and full verification | Migration 030 locally applied in pass 1; other environments remain unverified. | Required at checkpoint: fresh/populated upgrade, rerun/drift, wheel resources, typing, relevant regressions and exact-commit hosted evidence. |

Do not confuse “recorded” with “resolved”: the pass reporting rule is being followed, but most Slice 1 acceptance remains open. The focused pass count establishes the executed subset, not the entire predecessor test matrix. In particular, inspect conflicting operation kind/revision/reversal target and reversal retries after later changes rather than assuming reason/actor tests cover them.

### Proposed method to continue

1. **Finish the current contract pass.** Add the small replay-version, command-negative and malformed-history tests above; clarify supported database-role history guarantees. Keep this change confined to Slice 1.
2. **Complete traversal correctness as the next bounded pass.** Choose and document a consistent-read strategy that composes with existing transaction/lock ownership. Bound the frontier, detect examined-graph invalidity, and test shared budgets and exact limits. Do not add graph repair.
3. **Prove Slice 1 under concurrency and close its evidence.** Use disposable PostgreSQL fixtures for reciprocal writes, both lockdown orders and overflow failure snapshots. Run applicable migration/package/full checks, then record the tested implementation commit and hosted result. A checkpoint may honestly say partial; it must not say Slice 1 closed while these criteria remain open.
4. **Proceed to Slice 2, then Slice 3.** Correct stopping evidence/retry semantics before the workspace submits decisions. End with the disposable acquisition-to-report user journey and browser tests already specified.

The only product dependency here is backend contract closure before consumers. UI mockups or planning may proceed independently, but implementing around known incorrect backend semantics would hide the defects rather than resolve them.

### Proposed explicit deferrals and return triggers

These are recommendations for operator decision, not silent changes to required acceptance. When adopted, copy them into the maintained roadmap/gap ledger with their trigger and evidence requirement.

| Deferred work | Safe boundary now | Named later stage / return trigger | Evidence required then |
|---|---|---|---|
| Migration-028 command-request backfill | Reject historical replay when original identity cannot be proven; historical reads remain supported. | Historical command replay compatibility, only when a deployment needs replay of pre-030 operations. | Trusted reconstruction source, ambiguity refusal, upgrade and replay fixtures; never infer the original request from current state. |
| Cryptographic audit/history chaining and privileged tamper resistance | Claim tested chain consistency and append-only supported application behavior only. | Deployment audit-assurance milestone, before promising tamper evidence against privileged operators. | Threat model, key/checkpoint policy and tamper tests. |
| Broader database-role separation | First inspect existing privileges and state their actual limits; do not claim ordinary-role protection if absent. | Deployment privilege-hardening milestone, before use by a separately permissioned runtime identity or any operational immutability claim. | Migration/runtime role separation, negative UPDATE/DELETE tests and retained-history guarantees. If ordinary-role immutability remains current acceptance, implement it now instead of silently deferring it. |
| Invalid graph repair | Detect/report examined corruption; do not mutate on read or infer completeness from partial traversal. | Governed data-repair/recovery milestone, triggered by a real repair requirement and approved repair authority. | Provenance-preserving repair proposal, authorization, history/audit, rollback and failure tests. |
| New provider cost accounting or automatic deadline enforcement | Label unverified limits as operator-reported; preserve runtime unknown outcomes. | Bounded long-running execution milestone, before making measured budget/deadline stopping claims. | Durable runtime records, enforced limits and verified stopping references. |
| RecoveryContext, fence clearing, restoration and backups | Keep the restrictive recovery-bootstrap fence and current documented stop boundary. | Recovery authority design milestone before any restoration-completion implementation. | Reviewed authority contract followed by reconstruction/restore drills and preserved history/provenance. |

Migrate-before-serve, caller/system limitation separation, honest overflow, replay identity and known error handling are current correctness requirements, not candidates for deferral. Distributed crash atomicity remains an explicit provider-session limitation; do not reopen it as a hidden dependency of relationship work.

Decision recorded: the user approved the continuation order and bounded deferrals above. Retain the original closure requirements except for the explicit deferrals and return triggers in the table. The implementation remains uncommitted and partially verified until Slice 1 acceptance and its required evidence are completed.

## Slice 1 — pass 3 record: replay-negative matrix and grant reconciliation

Completed the checkpoint's current-contract additions without starting graph traversal work:

- Added same-operation mutation retries with a changed command kind or expected revision; both are rejected as conflicting identity reuse.
- Added a reversal exact retry after a later mutation, confirming the original reversal result is returned, and verified a changed reversal target conflicts.
- Added stored command metadata probes for an unknown version and an unexpected schema field; neither is accepted as a replay.
- Added malformed history fixtures with wrong relationship/task identity in resulting-state payloads; reads reject them without rewriting the persisted payload.
- Inspected effective local PostgreSQL privileges read-only. session_user/current_user is research_agent, the role owns source_relationship_changes and is a superuser, and effective SELECT/INSERT/UPDATE/DELETE are all true. This local identity cannot evidence least-privilege runtime protection.

Verification:

- Focused negative subset — 11 passed.
- Full tests/integration/test_source_dependence_contract.py — 25 passed.
- python -m ruff check src tests/integration/test_source_dependence_contract.py — passed.
- git diff --check — passed.
- The database grant inspection was read-only. No grant, role, or table mutation was performed.

Findings and risks:

- The local PostgreSQL identity is superuser/table owner; ordinary application-role UPDATE/DELETE denial is not demonstrated. Do not claim database-enforced history immutability from this environment.
- Replay tests now cover the checkpoint's identified command-kind/revision/reversal-target/version/schema cases. They remain focused contract evidence, not the full Slice 1 acceptance matrix.
- The working changes remain uncommitted; no full suite, packaging/upgrade matrix, strict typing, or hosted run has been performed on this tree.

Blocked criteria after this pass:

- History-read contract is tested for the current corruption matrix but still needs the applicable full Slice 1 verification and supported-role guarantee/claim boundary.
- Traversal snapshot consistency, frontier bound/omission indicator, exact and exceeded shared budgets, invalid examined-graph detection, reciprocal-edge concurrency, lockdown orderings, and cycle-overflow atomicity remain open.

Recommendations:

- Closure-required: retain only the tested chain-consistency and application behavior claims unless verification under the supported least-privilege runtime identity proves stronger row protections. If ordinary-role immutability remains a hard acceptance criterion, provide/use a non-superuser runtime role and add negative UPDATE/DELETE tests before Slice 1 closure.
- Required next pass: proceed to graph traversal correctness as approved, keeping report/planner consumers on the same explicit consistent-read and bounded-budget contract.
- Required before Slice 1 closure: complete reciprocal-edge/lockdown/overflow concurrency proofs, applicable full local checks, packaged migration verification, and hosted verification of the exact implementation commit.
- Deferred by approved checkpoint: separate role-provisioning/hardening work until a permission-separated runtime identity or an operational immutability claim is in scope; privileged-database tamper resistance remains deferred.

## Slice 1 — pass 4 record: bounded, stable traversal

Implemented the approved graph-read pass:

- Direct graph projection takes a task-row SHARE lock before capability/source/adjacency reads. SnapshotService takes the same lock as its first database operation. Both preserve caller-owned transactions and do not commit, roll back, or change transaction isolation.
- All supported source-relationship writers take the task-row UPDATE lock first. The shared lock therefore holds the graph stable against those writers through the caller transaction. The lock order remains task before security for relationship writes; the direct projection performs an unlocked capability read only after its task lock.
- Traversal uses one request-wide visited-node and distinct-relationship budget across roots. Adjacency queries are capped at max_examined_relationships + 1 rows, so a one-over lookahead proves edge overflow without unbounded result materialization. With configured maxima, there are at most 100 adjacency queries and 501 fetched rows per query (at most 50,100 adjacency rows per traversal); the cycle proof has the same per-query and node bounds.
- Frontier output is separately capped by max_frontier_sources and exposes frontier_omitted. Snapshot root overflow merges with graph frontier within that cap rather than serializing the full omitted-root tail.
- Examined active derived-from edges are checked for directed cycles. Invalidity is distinct from truncation: invalid results are incomplete even if traversal was exhaustive, and both flags can be true when corruption is found in a truncated view. Common-origin triangles remain valid pairwise relationships.
- Reports preserve the invalid projection and add an explicit limitation; cycle planning asks the operator to review invalid directed dependence. Unknown dependence remains explicit.
- Cycle-proof validation now uses distinct edge accounting, bounds adjacency fetches, enforces the visited-node and depth limits, and rejects incomplete proofs.

Regression coverage added for exact and one-over edge limits, exact node/depth boundaries, shared-root budgets, duplicate edge encounters, high fan-out and bounded/deterministic frontier, omitted SnapshotService roots, directed-cycle detection/report/planner surfacing, valid common-origin triangles, direct projection and SnapshotService reads racing a relationship mutation, and cycle-proof node/edge overflow with unchanged relationship/history/audit counts.

A final fingerprint regression found a consumer invalidation gap during this pass: after a relationship changed, the planner's dependence-specific basis fingerprint changed but the report review fingerprint did not. The test failed before the fix. The shared report/planner evidence fingerprint payload now includes the available source-dependence projection unconditionally, so both bases invalidate as the relationship graph changes. Regression assertions cover both the first edge and a subsequent graph change.

Verification:

- Focused fingerprint regression before fix — failed as expected because the report fingerprint stayed unchanged after a graph change; reran after fix: 1 passed, 35 deselected, 4 warnings in 2.08s.
- pytest -q -o addopts='' tests/integration/test_source_dependence_contract.py — 36 passed, 78 warnings in 13.02s. Warnings are FastAPI on_event deprecations from the existing app startup hook.
- python -m ruff check src tests/integration/test_source_dependence_contract.py — passed.
- python -m mypy src — passed (87 source files), rerun after the fingerprint fix.
- git diff --check — passed.
- Concurrency fixtures used disposable task/source data in the local PostgreSQL integration database. They observed the reader return the active graph before the blocked writer retracted the edge; final persisted state contained the retraction.

Findings and risks:

- Stability is lock-protocol consistency, not an independent MVCC snapshot: all supported relationship writers must continue to take FOR UPDATE on the same task row before changing graph state. Direct database writes that bypass the protocol, including the local superuser, are outside this guarantee.
- The shared task lock lasts through the caller-owned transaction and can delay relationship writes for the duration of report, planning, readiness, or snapshot work. Current report/snapshot routes configure REPEATABLE READ before their first query; the lock additionally protects graph consistency in existing READ COMMITTED consumer transactions.
- The 50,100 adjacency-row ceiling is an explicit worst-case upper bound, not the usual cost. It is bounded but could still be expensive under adversarial dense/high-fan-out graphs; query count and fetched-row count are not the same as database execution cost.
- Cycle detection is limited to the examined active directed edges. A detected cycle is definitive invalid evidence; absence of a detected cycle in a truncated view does not establish global acyclicity. Graph repair remains out of scope.
- The report fingerprint defect was exposed by this pass's regression and fixed by including source-dependence projection in the shared evidence fingerprint payload. This regression protects both report-review and planner dependence bases from silently remaining current after graph changes.
- The implementation is still uncommitted. The full repository suite, upgrade/package matrix, hosted exact-SHA run and remaining concurrency/lockdown closure checks are not yet recorded for this tree.

Blocked criteria after this pass:

- Slice 1 is not closed. Reciprocal-edge concurrent mutation, both mutation/lockdown orderings, and cycle-proof overflow proof under those security races remain for the following pass.
- Full Quality, migration 030 fresh/populated upgrade and rerun/drift checks, packaged migration-resource verification, and hosted verification of the exact implementation commit remain required.
- Least-privilege database history protections remain explicitly deferred to the approved deployment privilege-hardening return trigger; current claims are limited to supported application append behavior and validated history reads.

Recommendations:

- Required next pass: use disposable PostgreSQL races to prove reciprocal-edge uniqueness and both lockdown orderings; include exact state/history/audit assertions for rejection and success, plus cycle-proof overflow under contention.
- Closure-required: run migration 030 against fresh and populated upgrade fixtures, verify rerun/drift and package resources, rerun full Quality/strict typing, then push and confirm hosted CI tested the exact implementation SHA.
- Recommended hardening before high-volume use: profile bounded worst-case adjacency workloads and, if needed, reduce configured caps without weakening fail-closed overflow semantics.
- Deferred by approved checkpoint: standalone least-privilege runtime-role provisioning and privileged-database tamper resistance; revisit before using a separately permissioned runtime identity or claiming operational history immutability.

## Review after pass 3 — what changed and how to address it

This review inspected the updated pass record, working diff, test names, traversal implementation and snapshot call sites. No implementation or database changes were made, and the recorded 25-test result was not independently rerun. HEAD remains `35550b8`; migration 030 and the same three modified files remain uncommitted.

### Changes since the previous review

- Pass 3 adds the missing command-kind/revision/reversal-target and metadata-version/schema negatives, plus wrong relationship/task history-state fixtures. These close the previously identified focused-test omissions at the recorded local-evidence level. Do not request the same pass again absent a new failure.
- The privilege question now has a concrete answer: the recorded local account is both table owner and superuser. Chain validation can detect tested inconsistent changes, but the runtime identity can update/delete rows. Use the bounded claim “history is appended by supported application operations and validated on history reads.” Do not call this database-enforced immutability.
- The file now records approval of the continuation order and bounded deferrals. Follow that recorded scope: role provisioning and privileged tamper resistance are later deployment work, with the existing return triggers. Required graph correctness and remaining verification have not been deferred.
- No graph traversal, stopping, workspace or browser implementation changes have been added by this pass. Slice 1 is still open.

### Additional traversal details found in code review

`_validate_no_cycle()` currently limits examined encounters and depth but has no explicit `max_visited_sources` check. It increments the edge counter each time a relationship is encountered, including repeated visits to the same relationship via another endpoint. Its adjacency query also has no explicit row limit. This differs from the proposed shared contract of bounded distinct visited sources/relationships and bounded fetches. These are code-inspected gaps; the review did not execute an overflow reproduction.

Fix them as part of the already-required traversal pass, not as a new slice: use explicit visited-node and distinct-relationship accounting, bounded adjacency fetching/lookahead, and stable rejection when a complete cycle proof cannot be established. Clarify separately the bound on returned records, database query count and repeated fetch work; a bounded output is not proof of bounded physical database work.

### Concrete next-pass method

1. **Define transaction ownership before editing traversal.** Inventory direct graph reads, SnapshotService, report reads, planning and stopping reads. A stable graph inside a changing evidence snapshot is insufficient for consumers that claim a consistent basis. Prefer an explicitly owned consistent-read transaction for standalone read paths; choose isolation before its first query. For existing writer-owned transactions, preserve the caller's locks and transaction, and prove the supported writer protocol stabilizes relevant reads or provide an appropriate caller-level snapshot strategy. Do not open a fresh independent snapshot that loses the caller's pending state, change isolation mid-transaction, or commit/rollback inside a read helper.
2. **Make the limits executable.** Apply one request-wide budget across roots: 100 visited nodes, 500 distinct examined relationships, 8 hops and a separately capped frontier sample. Give omitted frontier entries an honest indication without requiring an unbounded exact list/count. Apply the compatible budgets to cycle proof; reject rather than accept an incomplete proof.
3. **Separate incomplete from invalid.** Truncation means unexplored data remains. A directed cycle in inspected active derivation edges means invalid data was observed. Preserve both facts where applicable; report/planner consumers must not infer completeness or independence. Symmetric common-origin cycles remain valid; repair remains deferred.
4. **Write the boundary tests before broader integration.** Cover exact limit versus one-over, duplicate edge encounters, shared-root budgets, bounded high fan-out, stable frontier ordering, and a concurrent commit during multi-query traversal. Confirm the documented snapshot semantics at the consumer boundary as well as the direct endpoint.
5. **Then finish concurrency and closure evidence.** Reciprocal graph mutations, both lockdown orders and cycle-proof overflow must leave complete state/history/audit outcomes. Follow with migration 030 fresh/populated upgrade/rerun/drift, packaged resources, strict typing, applicable regression checks and hosted verification for the eventual implementation commit.

### Disposition of the latest recommendations

| Recommendation | Action now | Later boundary |
|---|---|---|
| Stronger history protection | Correct the maintained guarantee wording before closure; do not use the superuser result as a successful denial test. | Runtime/migration role separation at the approved deployment privilege-hardening milestone. |
| More replay/history negative tests | Treat pass 3's recorded cases as provisionally addressed; retain them in the closure suite. | Revisit only on schema evolution, a new defect or a newly supported command. |
| Graph snapshot/budget work | Required next pass, including cycle-validator node and distinct-edge limits described above. | Not deferred. |
| Reciprocal-edge, lockdown and overflow proof | Required following the traversal change, before Slice 1 closure. | Not deferred. |
| Migration/package/full/hosted checks | Required at the implementation checkpoint; 25 focused passes are not a substitute. | Not deferred. |
| Stopping/workspace work | Preserve Slice 2 and Slice 3 order after Slice 1 closure. | No additional capability expansion until this workflow is usable. |

Recommended decision: continue directly with the bounded traversal pass under the approved scope. No new architecture approval is needed merely to repeat the now-resolved local privilege finding; a proposal to promise stronger deployed immutability would be a separate scope change.

## Slice 1 — pass 5 record: reciprocal-write, lockdown and overflow races

Added deterministic PostgreSQL integration races using real backend PIDs and pg_blocking_pids checks:

- Two simultaneous reciprocal derived_from creates serialize on the task row. Exactly one relationship/current row, one revision-1 CREATE history record and one source-dependence audit event persist; the second request sees the accepted edge and rejects the cycle.
- Both source-mutation/security-lockdown orderings are exercised. When mutation holds the security SHARE lock first, it commits its complete relationship/history/audit change and lockdown follows. When lockdown holds the security UPDATE lock first, the waiting mutation is denied after lockdown commits and leaves no relationship/history/audit row. Each ordering records exactly one lockdown transition.
- A cycle-proof edge-budget overflow is paused after its bounded adjacency query while lockdown attempts the security row. PostgreSQL confirms the blocker; after release, the mutation fails closed, rolls back, and releases the lock so lockdown succeeds. Relationship identities/revisions/latest-change IDs, history count and audit count match the pre-race baseline.
- The security fixture restores all persisted singleton fields and removes only the transition row written by this test actor. SQL listeners and blocking gates are removed/released in finally cleanup.

An assertion review found the earlier overflow tests filtered the event table using the wrong event name (source_dependence_changed instead of canonical source.dependence_changed). The query has been corrected in the overflow checks, so their no-partial-audit assertion now measures the actual event type instead of vacuously finding zero events.

Verification:

- Targeted race set — 4 passed, 36 deselected, 10 warnings in 3.46s.
- Full source-dependence contract suite — 40 passed, 86 warnings in 17.21s. Warnings are existing FastAPI startup on_event deprecations.
- Security API and interruption-ordering suites — 46 passed, 20 warnings in 12.50s.
- python -m ruff check src tests/integration/test_source_dependence_contract.py — passed.
- python -m mypy src — passed (87 source files).
- git diff --check — passed.

Risks/findings:

- These tests establish the application lock protocol and service-level transaction outcomes on local PostgreSQL. They do not cover direct SQL/bypass writers, alternate isolation/deployment topology, or database-privileged tampering.
- The test-only reset fixture touches the singleton security state; it preserves and restores the full row and is intended for serial integration-suite execution. Do not run these global-security-state integration tests concurrently against the same database.
- Security/order and graph budget behavior passed, but the migration/package/full-repository/hosted implementation-checkpoint evidence remains outstanding. Slice 1 and today's overall slices are not closed.
- The working tree remains uncommitted; the temporary directive remains ignored by Git.

Recommendations / next work:

- Required closure checkpoint: inspect the integrated diff, run migration 030 fresh-install plus populated-upgrade/rerun/drift and packaged-resource checks, then run full repository Quality and strict typing. Record exact commands/results; do not substitute the focused counts above for full Quality.
- If local closure checks pass, commit the implementation baseline, record its SHA, push, and verify hosted Quality/browser CI report that exact SHA. Only then update maintained source-of-truth, roadmap and implementation-status docs in a separate documentation commit and complete the directive with both SHAs, hosted URL/tested SHA, migration count, clean-tree state and deferred limitations.
- Keep role separation and privileged tamper-resistance claims deferred as previously approved; do not expand this closure pass into runtime-role provisioning.

## Slice 1 — pass 6: integrated verification and review-scope correction

Reviewed pass 4/5 findings and the integrated working diff. Preserved the existing
uncommitted implementation. Addressed the remaining local verification gap and a
regression revealed by full-suite execution; no role provisioning or graph repair
was introduced.

Changes made in this pass:

- Added `test_source_dependence_upgrade.py`: builds a disposable real pre-030
  schema, populates task/source/current/history rows, applies migration 030 and
  reruns it. It proves original history and current state are unchanged and legacy
  command metadata remains null. The schema and its data are removed by transaction
  rollback. Existing wheel verification separately covers checksums/drift.
- The initial full suite exposed two failures: unrelated source additions reopened
  completed narrow claim and agent reviews. Pass 4's unconditional inclusion of
  the whole dependence projection caused this regression.
- Corrected fingerprint scope: broad/report/dependence reviews retain the entire
  projection; narrow reviews track the declared component connected to referenced
  sources. Incomplete/invalid projections remain conservative. Connectivity only
  determines which changes invalidate a review; it does not infer transitive
  common-origin facts or independent corroboration.
- Added `test_source_dependence_review_basis.py` to prove an unrelated component
  leaves a narrow basis unchanged, while a direct relevant edge and a subsequent
  connection into that component invalidate it.

Evidence obtained in this pass:

- Initial `python -m pytest -ra`: 2 failed, 1611 passed, 5 skipped; both failures
  were the review-scope regressions above, before correction.
- Corrected objective-review, planning-completion, source-dependence and populated
  upgrade suites passed (59 cases); the additional narrow-component test passed.
- `python -m ruff check .` and `python -m mypy src` passed (87 source files).
- `python scripts/check_conformance.py` passed traceability checks; this remains
  distinct from behavioral/release conformance.
- Smoke and disposable prototype verification passed, including fresh application
  of 30 migrations, no-op rerun and real HTTP lifecycle/restart persistence.
- `python scripts/verify_wheel.py --database` passed again after the fingerprint
  correction: 30 packaged resources match source checksums; clean base install
  without AWS, populated upgrade, rerun, checksum-drift rejection and draft checks
  passed. Its disposable database was removed.
- Final `RUN_BROWSER_TESTS=1 python -m pytest -ra`: **1620 passed, zero skips,
  596 warnings in 196.62s**, including all five existing browser cases. Warnings
  are startup deprecations and Pydantic alias warnings; no test failures remain.

Remaining boundary: these are local working-tree results, not hosted evidence for
an implementation SHA. Changes remain uncommitted. Preserve the separate commit/
hosted verification gate and subsequent maintained-documentation closure; do not
reuse earlier CI as evidence for this tree. Stopping correctness and new workspace
interactions remain Slices 2 and 3. The existing five browser cases do not establish
those new interactions. Approved role/tamper-resistance deferrals remain unchanged.

## Slice 1 — implementation baseline committed locally

- Implementation commit: 4fa785b98dfaf33b372284cc4b271aa753ab386e (Close source dependence contract and traversal gaps).
- Browser-enabled full suite rerun on the committed tree: 1620 passed, zero skipped, 595 warnings in 152.30s. One earlier full-suite attempt had 1619 passed and a single unrelated source-registry audit event-order assertion failure; that test passed standalone and the complete rerun passed. Keep this flake noted rather than treating its first result as green.
- Wheel verification: 30 packaged migration resources matched checksums; fresh schema/base install, populated upgrade, rerun, migration-checksum drift rejection, and draft/resource checks passed. Disposable database removed.
- Ruff, strict mypy (87 source files), conformance traceability, and commit diff whitespace checks passed.
- Local worktree is clean after commit; main is ahead of origin/main by one commit.
- Push and hosted exact-SHA Quality/browser verification are still pending. This is not yet the hosted implementation baseline; do not update maintained source-of-truth/roadmap/implementation-status documents until the exact hosted run passes.
- The active execution environment cannot perform remote operations. Resume by pushing this exact commit SHA from an authorized environment, then record the hosted run URL and tested SHA before the separate documentation closure commit.

## Hosted implementation verification — 23 September 2026

Implementation SHA: `4fa785b98dfaf33b372284cc4b271aa753ab386e`.
Hosted Quality: [run 35676307231](https://github.com/SkillSpringAI/Gnomon/actions/runs/35676307231).
Verified directly via run/job metadata: tested SHA equals the implementation SHA;
`checks`, `minimal-install` and `browser` all completed successfully. Browser
regression step and prerequisite installation/migration steps passed. Earlier
push/hosted-pending notes above are historical and superseded by this record.

Maintained documentation is being updated in a separate documentation-only commit.
The final closure below will identify that commit separately; this hosted run is
not evidence for a later documentation commit. Closure applies to Slice 1 only;
Slices 2 and 3 remain open.

## Final Slice 1 closure — 23 September 2026

- Status: Slice 1 source-dependence contract/traversal closure complete for the
  supported application scope. The overall three-slice directive remains active:
  Slice 2 stopping correctness and Slice 3 new workspace interactions are open.
- Implementation SHA: `4fa785b98dfaf33b372284cc4b271aa753ab386e`.
- Documentation SHA: `139213a4f5c4616150164997cf434bc36d084f72`
  (`Record hosted source dependence closure and remaining scope`). This separate
  commit contains only maintained source-of-truth, implementation-status, roadmap
  and migration documentation.
- Hosted implementation evidence: [Quality run 35676307231](https://github.com/SkillSpringAI/Gnomon/actions/runs/35676307231).
  Tested SHA is exactly `4fa785b98dfaf33b372284cc4b271aa753ab386e`.
  `checks`, `minimal-install` and `browser` completed successfully, including the
  browser prerequisite, migration and regression steps. No claim is made that
  this earlier run tested documentation commit `139213a`.
- Local implementation evidence: recorded browser-enabled rerun 1,620 passed,
  zero skips; 30 migration resources with fresh/populated upgrade, rerun/drift,
  clean base install, HTTP restart, lint, strict typing and conformance checks.
  Retain the earlier intermittent source-registry event-order assertion failure
  and its successful standalone/full reruns as historical verification evidence.
- Documentation validation: conformance traceability and git diff whitespace
  checks passed. No application code was changed in the documentation commit.
- Working tree: clean tracked tree after the documentation commit; this temporary
  directive remains ignored. Documentation commit is local; it was not pushed in
  this closure task and has no hosted verification claim.

Deferred limitations and return triggers:

1. History is appended by supported application operations and validated on read;
   the inspected local account is superuser/table owner. Runtime/migration role
   separation returns at deployment privilege hardening before operational
   immutability claims; cryptographic/privileged tamper resistance returns at
   deployment audit assurance.
2. Legacy pre-030 rows lack command identity and refuse replay. Backfill returns
   only with a concrete compatibility need and trusted reconstruction evidence.
3. Invalid graphs are detected within examined edges, not repaired; partial reads
   cannot establish global acyclicity. Repair requires governed recovery design.
4. Stability assumes supported task-lock writers; direct SQL/bypass writers are
   outside the guarantee. Profile dense adjacency before high-volume use.
5. Automatic independence/causal inference, authenticated multi-operator identity,
   recovery completion, backup reconstruction and autonomous scheduling remain
   under their separately documented design gates. Operator-reported limits must
   not become measured runtime evidence without the later execution controls.
6. Stopping correctness and new relationship/stopping browser interactions remain
   required next work, not closed or silently deferred by this record.

## Slice 2 — pass 1: canonical stopping commands and replay (23 September)

Status: incremental local checkpoint; Slice 2 is not closed. Changes are uncommitted.

Regression first: four new API/service tests failed on the baseline. Exact replay
returned 409 when the server had added limitations, while changed expected status,
expected revision and trusted actor incorrectly returned the accepted result.

Implementation:

- New additive migration 031 adds nullable `command_request` to stopping history.
  Prior migrations were not edited. Migration 031 was applied locally before tests.
- New accepted commands retain a version-1 CONCLUDE request independently of the
  server-derived decision. All model-normalized request fields except operation ID
  participate; the existing operation ID locates the record. Lists are deduplicated
  in encounter order. Order remains significant and future normalization changes
  need an explicit compatibility policy.
- Replay verifies task, trusted actor type/ID and complete canonical request,
  including expected state/revision/fingerprint. It returns historical accepted
  state, not the current projection, and still checks current mutation authority.
- Legacy rows lacking original command metadata remain readable but replay is
  refused. No command backfill is inferred from derived limitations or current state.
- Trusted actor context rejects unsupported actor types and blank IDs at service
  construction. No caller-supplied actor field or authentication system was added.

Verification:

- Before fix: four new regression cases failed as expected.
- After fix: `python -m pytest -q tests/integration/test_stopping_replay.py
  tests/integration/test_stopping_decisions.py` — 15 passed. This includes existing
  concurrency/audit rollback tests and eight new replay cases: server-added
  limitations, changed preconditions/actor, missing/unknown metadata, historical
  output and current-authority refusal. The fixtures clean up their task data.
- `python -m ruff check .`, strict mypy (87 source files), conformance traceability
  and `git diff --check` passed. Existing FastAPI startup deprecation warnings remain.

Findings/limits:

- This fixes request identity, not the 20-entry limitation truncation. Caller text
  can still crowd out derived warnings; that remains required next-pass work.
- Legacy stopping replay compatibility is intentionally conservative, analogous
  to source-dependence replay. Public decision/history reads remain unchanged.
- Migration 031 must precede deployment of the updated ORM. Fresh/populated upgrade,
  rerun/drift, wheel verification, full regression and hosted exact-SHA evidence
  remain required before Slice 2 closure; focused results do not replace them.
- No claim is made for new workspace interactions or database-enforced immutability.

Incremental continuation checklist:

1. Next: preserve system-derived limitations separately or with an explicit bounded
   merge that cannot discard mandatory warnings; test maximum caller entries and
   exact retries against the preserved accepted output.
2. Then: validate no-cycle objective references and persist explicit cycle identity
   for objective references, with a deliberate compatibility rule.
3. Then: reconcile readiness with unresolved prior objectives/current reviews,
   contradictory evidence links, incomplete dependence and no-evidence cases;
   distinguish operator-reported runtime limits from verified runtime records.
4. Finally: verify fingerprint ordering, stale/authority/concurrency/failure outcomes,
   migration/package/full-suite checks and hosted evidence before closing Slice 2.

Do not skip these remaining steps merely because replay now passes. Keep this pass
uncommitted until its intended checkpoint is reviewed; no commit or push occurred.

## Slice 2 — pass 2: preserve derived limitations (23 September)

The operator approved pass 1 and requested this next incremental pass. Pass 1
changes remain intact and uncommitted; this pass adds no new migration.

Regression first: a request with 20 distinct caller caveats displaced the derived
source-independence warning. The new API test failed on the old merge (one failed,
two passed before the fix).

Changed the acceptance merge to retain every non-satisfied readiness warning first,
then all distinct caller caveats in encounter order. No entries are truncated.
The request still accepts at most 20 caller entries; the output count is bounded by
20 plus the fixed server readiness-item count (currently six, hence at most 26).
Identical caller/system wording appears once. This is a count bound, not a new
character/byte-size guarantee. A later readiness expansion must preserve and test
this explicit bound rather than reintroducing a silent output cap.

The stored combined limitations and canonical original command remain separate.
Retries and history reads return accepted historical output without re-merging
against today's readiness. Previously accepted history is not rewritten to invent
warnings lost before this fix. No response-field or database schema change is
needed; output limitation lists already permit more than 20 entries.

Tests and verification:

- Added three integration cases: maximum caller entries with separate system
  warnings; overlapping caller/system text with deterministic deduplication;
  rejection of 21 caller entries without lifecycle or history mutation.
- Strengthened the acceptance fixtures to include both an unassessed hypothesis
  and source-dependence uncertainty, proving multiple warnings survive.
- Assertions cover immediate result, exact retry, persisted current read,
  immutable history output and report projection. Exactly one stopping audit
  event remains after the retry.
- Stopping limitation/replay/decision and report suites passed (26 cases);
  strengthened multiple-warning cases reran afterward: 3 passed.
- Ruff, strict mypy (87 source files), conformance traceability and whitespace
  checks passed. Existing startup deprecation warnings remain.

Remaining acceptance and next pass:

- Required next: no-cycle objective reference validation and explicit cycle
  identity/compatibility for objective references.
- Still required: readiness alignment with prior unresolved work/current reviews,
  contradictory links and empty/incomplete evidence; operator-reported versus
  verified runtime limits; canonical fingerprint and concurrency/failure coverage.
- Full Slice 2 regression, migration 031 fresh/populated upgrade/rerun/drift,
  packaging and exact-SHA hosted checks remain closure gates, not claimed here.
- Legacy missing-command replay, history protections and all approved security
  deferrals are unchanged. No new workspace interaction is claimed.

Slice 2 remains open. This pass and the approved pass 1 remain uncommitted for
incremental review; no commit or push was made.

## Slice 2 — pass 3: cycle-qualified objective references (23 September)

Implemented the approved objective-reference validation pass.

- Added nullable migration 032 and ORM/domain support for
  `objective_cycle_number` on accepted stopping decisions. Legacy decisions
  remain readable with a null cycle identity.
- Objective indices now fail with a controlled stopping conflict when no cycle
  exists, instead of indexing the latest-cycle list and raising an unhandled
  error.
- An explicitly named cycle must exist; an unknown cycle is rejected separately
  from an out-of-range objective index.
- Compatibility rule: pre-032 clients may omit the cycle number only when
  providing no objective indices. If objective indices are provided without a
  cycle number, the request resolves against the latest cycle and stores that
  resolved cycle identity. Explicit cycle identity without objective indices is
  rejected as contradictory.
- Accepted current and historical decision representations retain the resolved
  cycle number. Canonical command replay remains based on the original request,
  so the compatibility resolution does not rewrite the accepted command.

Regression coverage:

- No-cycle objective reference returns 409 rather than an index error.
- Unknown cycle and invalid objective index are rejected.
- Omitted cycle identity resolves to cycle 1, persists in the response/current
  projection/history, and exact retry returns the historical decision.

Verification:

- `python -m research_agent.cli migrate` — applied migration 032.
- Focused stopping suites — 20 passed, 48 warnings.
- `python -m mypy src` — passed (87 source files).
- Ruff on changed stopping files and `git diff --check` — passed.

Risks/findings:

- The compatibility rule deliberately binds an omitted objective cycle to the
  latest cycle at acceptance. New clients should send the explicit cycle number;
  later cycle planning does not reinterpret an already accepted decision.
- Legacy stopping decisions remain cycle-unqualified. They are readable, but
  their historical objective references cannot be upgraded without trusted
  reconstruction evidence.
- Migration 032 is applied locally but the combined Slice 2 changes remain
  uncommitted. Fresh/populated upgrade, rerun/drift, packaging, full regression,
  and hosted exact-SHA checks remain open.

Recommendations / next work:

- Review and approve this compatibility rule before proceeding.
- Then reconcile readiness with unresolved prior objectives, current/stale
  reviews, contradictory evidence links, incomplete dependence and no-evidence
  cases.
- Keep operator-reported runtime limits separate from verified runtime records.
- Defer Slice 2 commit/hosted closure until migrations 031/032 and the complete
  stopping contract have been verified together.

## Slice 2 — pass 4: readiness reconciliation and runtime attribution (23 September)

Implemented the approved readiness-alignment pass without adding an accounting
system or upgrading the advisory checklist into a semantic conclusion.

- Unresolved objectives are now collected across cycles and completed current
  reviews remove their resolved objective from the stopping warning. Stale
  objective reviews are surfaced as a separate `stale_reviews` readiness item.
- Contradictory claims include both contested/contradicted claim status and
  explicit contradicting evidence links.
- Source-dependence readiness remains unknown when sources exist, with a more
  specific incomplete/invalid limitation when the bounded projection cannot
  establish a complete valid graph.
- Investigations with neither sources nor structured claims now expose an
  attention-level `no_evidence` item instead of presenting a satisfied
  readiness entry.
- Resource-limited decisions explicitly label supplied runtime limits as
  operator-reported and not system-verified; a resource-limited request without
  runtime evidence receives a separate missing-evidence limitation. No measured
  runtime claim or new accounting path was introduced.

Verification:

- Stopping, objective-reference, replay, limitation, objective-review and
  planning-completion suites — 39 passed, 90 warnings.
- Strict mypy (87 source files) — passed.
- Ruff and `git diff --check` — passed after import normalization.

Risks/findings:

- Readiness still depends on the existing objective-review fingerprint rules;
  it reports stale reviews but does not repair or rewrite them.
- Runtime evidence remains operator-supplied text. The new label prevents it
  from being mistaken for verified runtime records, but it does not validate
  that a referenced runtime record exists.
- Slice 2 changes, including migrations 031/032, remain uncommitted. Full
  migration upgrade/rerun/drift, packaging, full regression and hosted exact-SHA
  checks remain open.

Recommendations / next work:

- Review this readiness and runtime-attribution pass, then reconcile canonical
  fingerprint ordering and stale/authority/concurrency/failure outcomes.
- Add explicit validation for any future structured runtime-record reference
  before making measured budget/deadline claims.
- Keep Slice 2 closure separate from Slice 3 workspace/browser work.

## Slice 2 — pass 5: canonical fingerprints and failure-path hardening (23 September)

Implemented the approved fingerprint and transaction-outcome hardening pass.

- Evidence fingerprints now use explicit compact canonical JSON serialization,
  stable identifier ordering for hypotheses, claims and sources, and sorted
  readiness identifier/label collections. Equivalent evidence snapshots no
  longer receive different fingerprints solely because those collections were
  assembled in a different order.
- Added a regression proving reordered evidence collections preserve the same
  fingerprint.
- Extended the audit-failure regression to retry the exact operation after the
  failed transaction; the retry succeeds, confirming the failed attempt does
  not consume the operation identity or leave a partial lifecycle transition.
- Existing stale-basis, current-authority denial, one-winner concurrency, and
  audit rollback coverage remains in the focused stopping suite.

Verification:

- Stopping, replay, limitation and objective-reference suites — 22 passed, 52
  warnings.
- Strict mypy (87 source files) — passed.
- Ruff and `git diff --check` — passed.

Risks/findings:

- Fingerprint canonicalization now treats evidence collections as order
  independent, but task-internal ordered structures (for example objective
  ordering and review history) remain intentionally stateful and are still
  represented in the task payload.
- The suite proves rollback and retryability for an audit staging failure, but
  does not inject database-commit or migration-application faults.
- Slice 2 remains uncommitted; migration upgrade/rerun/drift, packaging, full
  regression, and hosted exact-SHA checks remain open.

Recommendations / next work:

- Keep the ordering policy documented if future clients depend on objective or
  review ordering as part of the evidence basis.
- Add a database-level failure test only if the repository gains a reliable
  transaction-fault injection seam; avoid coupling tests to driver internals.
- Proceed to the Slice 2 full local verification and migration/package closure
  pass before committing the implementation baseline.

## Slice 2 — review checkpoint and revised gap-closing order (23 September)

Review scope: current uncommitted passes 1–5 against the stopping contract and
planner behavior. HEAD remains 139213a; the Slice 2 implementation and migrations
031/032 are still uncommitted. This checkpoint does not close Slice 2.

Confirmed improvements:

- Accepted command identity is stored separately from derived limitations;
  retries check actor/task/command and return the historical result under current
  authority. Regression coverage includes changed preconditions, legacy metadata,
  actor changes, historical replay, and authority denial.
- Derived warnings precede caller limitations without truncation. Objective
  references now persist a cycle identity, including the documented omitted-cycle
  compatibility rule. Audit staging rollback can be retried with the same operation.
- Readiness adds contradiction links, stale reviews, no-evidence warnings and
  runtime attribution; evidence collection ordering is normalized.

Findings to close before the full verification pass:

1. P1 — Stopping readiness misses outstanding objectives on blocked/failed cycles
   whose explicit unresolved_objectives list is empty. The planner falls back to
   the cycle objectives; stopping readiness does not. A read-only in-memory probe
   reproduced both statuses: readiness returned satisfied / "No unresolved
   objectives are recorded" while the planner retained the original objective.
   Align objective selection with the planner's existing semantics, then apply
   current-review resolution. Add focused blocked/failed and prior-cycle tests.
   Decide planned-cycle handling explicitly instead of accidentally treating an
   empty unresolved list as evidence of completion.
2. P2 — An assessment with status unresolved is neither missing nor mixed, so
   stopping readiness emits no assessment warning for it. The planner explicitly
   handles unresolved_assessment. Add an explicit readiness warning and contract
   test; ensure acceptance, history, replay and reports retain the limitation.
3. P2 — Pass 4's aggregate test counts do not establish coverage of each new
   stopping behavior. The stopping tests explicitly exercise no-evidence and
   supplied runtime attribution, but lack dedicated assertions for prior-cycle
   objectives, current versus stale reviews, contradicting links, incomplete
   dependence, and missing runtime evidence. Add a small parameterized readiness
   matrix plus selected persistence checks. Planner tests alone cannot catch a
   divergence in the stopping consumer. Define whether stale_reviews means all
   historical reviews or only effective latest reviews; test superseded history.
4. P3 — The limitations comment still says 26 and excludes the additional
   resource-limit warning. Replace the numeric claim with an accurate bound based
   on derived readiness warnings plus the optional runtime warning and caller cap.

Next three bounded passes:

1. Correct readiness semantics and close the targeted test gaps above. Keep
   operator conclusion available despite warnings; readiness remains advisory.
   Review this diff before declaring the behavior complete.
2. Verify the combined Slice 2 changes: populated pre-031 upgrade with legacy
   stopping rows, fresh install, migration rerun/drift, wheel/prototype packaging,
   then the full regression suite. Include nullable legacy cycle/history reads and
   conservative legacy replay refusal. Freeze the version-1 command shape before
   release: pass-1 development metadata predates objective_cycle_number, so decide
   explicitly whether those local development receipts need compatibility rather
   than silently claiming every development version-1 receipt is replayable.
3. Commit the implementation baseline, obtain hosted Quality/browser evidence for
   that exact SHA, then update maintained docs in a separate commit and close the
   temporary directive with both SHAs, hosted URL and deferred scope. Existing
   browser results do not establish Slice 3 editing/submission coverage.

Known deferrals:

- Structured runtime-record validation belongs with measured runtime/accounting
  work; current text must remain explicitly operator-reported.
- Legacy cycle identity reconstruction requires trusted historical evidence.
- Database role hardening and privileged history tamper resistance remain at the
  previously named deployment/audit stages.
- Commit/connection-loss fault injection is separate transaction-resilience work;
  audit staging rollback does not prove ambiguous commit-outcome recovery. Do not
  claim that assurance from the existing test.
- Slice 3 workspace editing and browser interaction acceptance follows Slice 2
  closure; do not expand this corrective pass into that work.

Review validation: inspected service/models/migrations and stopping tests; ran a
read-only in-memory blocked/failed-cycle reproduction (both mismatches confirmed).
No full suite was rerun for this review, and no implementation files were changed.
Earlier pass test counts remain historical evidence rather than a fresh run.

## Slice 2 — pass 6: readiness gap corrections (23 September)

Implemented the approved corrective pass:

- Unfinished cycles retain their objectives even with an empty unresolved list,
  including blocked, failed, planned and running cycles. Completed-cycle review
  candidates can reopen when the effective review is stale or unresolved. Current
  completed reviews retain the existing planner resolution semantics.
- Added unresolved_assessment readiness warnings. Integration coverage verifies
  their preservation through acceptance, exact retry, current read, history and
  report output, including the maximum caller caveat list.
- Stale-review warnings consider the latest review per objective index within each
  cycle. Superseded reviews remain in history without independently warning.
- Corrected the limitations bound comment to include the optional runtime warning.
- Added dedicated readiness tests for every cycle status, prior-cycle objectives,
  current/stale/replacement reviews, unresolved assessments, contradiction links,
  and complete/incomplete/invalid dependence. Runtime tests cover supplied and
  absent evidence. Readiness remains advisory and does not prevent conclusion.

Verification: 37 focused unit/integration tests passed (58 existing FastAPI
startup deprecation warnings); strict mypy passed for 87 source files; Ruff and
final git diff --check passed. Test setup errors during development were corrected
before the successful run. No implementation commit was created.

Next checkpoint: inspect this corrective diff, then perform the combined migration,
packaging and full regression pass described above. Hosted exact-SHA closure and
maintained documentation remain pending. The existing latest-reviewed-occurrence
policy for duplicate objective text is unchanged; this pass does not redesign
planner objective identity. Previous runtime/accounting, historical reconstruction,
transaction-resilience and Slice 3 deferrals remain in effect.
## Slice 2 closure — hosted verification and documentation (23 September)

Implementation commit: `995f9cc9d0683cdbf331ec4f3708492d7b4231a4`.
Hosted Quality run: https://github.com/SkillSpringAI/Gnomon/actions/runs/35806845915
The run tested that exact SHA. `checks`, `minimal-install`, and `browser` passed.

Local closure evidence: 1,652 tests passed with browser enabled and zero skipped;
Ruff, strict mypy over 87 source files, conformance traceability, smoke, prototype,
fresh/restart HTTP, clean wheel, populated pre-031 stopping upgrade, migration rerun,
and checksum-drift rejection passed. Migrations 031 and 032 are included in the
implementation commit.

Maintained documentation commit: pending until this documentation change is
committed separately. Slice 2 is closed for its supported operator-controlled,
advisory stopping scope after that commit. Slice 3 workspace relationship editing
and stopping-submission browser acceptance remains next.

Deferred limitations recorded: operator-supplied runtime text is not measured or
verified; legacy objective-cycle reconstruction needs trusted historical evidence;
ambiguous-commit/connection-loss recovery is untested; database privilege and
privileged history tamper protection remain deployment/audit work; automatic
semantic stopping/reopening and authenticated multi-operator identity remain
outside this slice; duplicate objective text keeps the planner's current
latest-reviewed-occurrence policy.

Maintained documentation commit: `6e8376fbd5ce879122958dd2d156f00e2156a8c8`.
It updates source-of-truth, roadmap, conformance status and migration guidance in a
separate commit after implementation verification. Slice 2 is now closed for its
supported scope. Slice 3 is the next sequence item.

## Slice 3 — workspace relationship editing and stopping submission (23 September)

Slice 2 is closed at implementation `995f9cc9d0683cdbf331ec4f3708492d7b4231a4`
and documentation `6e8376fbd5ce879122958dd2d156f00e2156a8c8`. Slice 3 begins
from the existing credential-free workspace and the already-verified source-
dependence and stopping APIs.

Current gap review:

- The workspace displays source-dependence counts and limitations but has no controls
to create, correct, retract, reverse, or inspect relationship history.
- The workspace displays a stopping-decision summary but has no readiness panel or
operator submission form. The API already exposes readiness and evidence-bound
submission, so the browser must bind the form to the returned revision and
fingerprint and preserve conflict/retry behavior.
- Existing browser coverage has five cases for collection, review, recovery and
stale-state behavior. It does not cover relationship editing or stopping submission.
- Relationship endpoint semantics are already task-scoped and audited; UI work
must not duplicate mutation rules or infer independence from absent edges.

Recommended three bounded passes:

1. Add source-dependence workspace editing. Render source choices, relationship
kind/direction fields, current graph rows, and explicit create/retract/correct
actions. Refresh after each mutation and show history/unknown limitations. Add
browser coverage for a derived directional edge and a common-origin symmetric
edge, plus rejection feedback for stale or invalid edits.
2. Add stopping readiness and submission. Load readiness alongside the report,
show every attention/unknown item, require the current task revision and evidence
fingerprint, expose structured reason/rationale/limitations and source/claim/
objective/review references, and render accepted history. Add browser coverage for
successful submission, exact retry, stale-basis conflict, and current-authority
failure feedback.
3. Run the complete browser and local regression matrix, then close Slice 3 with
an implementation commit, hosted exact-SHA browser evidence, and a separate
maintained-documentation commit. Keep browser verification of the new controls
separate from the existing five-case baseline.

Acceptance constraints:

- UI remains operator-controlled; no automatic conclusion or inferred independence.
- Server remains authoritative for validation, capability checks, revisions, and
immutable history. Browser state is disposable and reload-safe.
- Preserve bounded graph overflow/invalidity language and all derived readiness
limitations. Do not hide warnings to make submission convenient.
- Keep relationship editing and stopping submission separate in commits or clearly
separated change groups so failures are diagnosable.

Known deferrals: authenticated multi-operator identity; automatic semantic stopping
or reopening; structured runtime accounting; legacy cycle reconstruction; ambiguous
commit recovery; database privilege/tamper hardening; and broader workspace redesign.

Review validation: inspected workspace template, report shape, source-dependence
routes/service, stopping routes/service, and existing five browser cases. No Slice 3
implementation or browser test was added in this review checkpoint.

## Slice 3 — pass 1: workspace relationship editor (23 September)

Added the first workspace interaction pass for declared source dependence:

- The workspace now renders source choices and supports creating directional
  `derived_from` declarations and symmetric `common_origin` declarations through
  the existing task-scoped API.
- Current projected relationships render with endpoint labels, kind, lifecycle and
  revision. Active rows expose an explicit retract action; every mutation reloads
  the report so server revisions and bounded/unknown graph limitations remain
  authoritative.
- Shared integration cleanup now removes relationship history and projections
  before deleting test tasks. The new browser test exposed this existing fixture
  gap during teardown and the cleanup fix was included in the pass.

Verification: all six workspace browser tests passed, including the new directional
and symmetric create/retract flow. Existing five cases remain green. This pass is
uncommitted and Slice 3 remains open.

Remaining relationship-editor gaps: correction/reversal UI, relationship-history
inspection, stale-edit/conflict feedback, and a richer graph/overflow presentation.
Stopping readiness/submission UI is still the next separate pass.

## Slice 3 — pass 2: stopping readiness and submission (23 September)

Added the workspace stopping-decision pass:

- The workspace loads `/stopping-decision/readiness` with the report and renders
  every readiness status/detail, including unresolved objectives and unknown
  dependence limitations.
- Operators can submit a structured reason, rationale and newline-separated
  limitation list. The request uses the current task status, revision and
  evidence fingerprint returned by the server; the server remains authoritative
  for stale-basis, capability and lifecycle conflicts.
- After acceptance, the report refresh renders the accepted decision and disables
  the submit action. No automatic conclusion or inference was added.
- Shared fixture cleanup now purges stopping decision projection/history as well
  as relationship rows before task deletion.

Verification: seven workspace browser tests passed (the original five plus
relationship editing and stopping submission), with existing browser behavior
remaining green. The stopping test verifies readiness display, submission, accepted
report output and disabled repeat submission. This pass is uncommitted.

Remaining Slice 3 gaps: relationship correction/reversal and history inspection,
richer graph overflow presentation, structured source/claim/objective/review
reference selection in the stopping form, explicit stale-basis/current-authority
browser conflict cases, and full local/hosted verification. Keep these in a
separate hardening pass before committing Slice 3.

## Slice 3 — five-slice continuation plan (23 September)

The relationship editor and basic evidence-bound stopping submission are approved.
The remaining work is divided into five slices, each completed through two passes:
implementation, then focused acceptance hardening.

### Slice 3A — relationship correction and reversal

Pass 1: add workspace controls for versioned relationship correction (direction or
lifecycle) and eligible reversal, reusing expected revision/change identity from the
server. Preserve explicit reasons and do not permit client-side state invention.

Pass 2: render relationship history and add browser coverage for correction,
reversal, stale revision rejection, expired reversal, and reload persistence.

### Slice 3B — bounded graph visibility

Pass 1: show examined edges, directional versus symmetric meaning, frontier nodes,
overflow reason, invalid-graph status and unknown-dependence language in a compact
workspace view.

Pass 2: add browser coverage for truncated node/edge/depth projections and invalid
directed graphs, verifying the UI never presents a partial graph as independence.

### Slice 3C — structured stopping references

Pass 1: extend the stopping form with source, claim, objective-cycle/index, review,
and runtime-limit reference controls. Populate only IDs returned by the current
report/readiness state and preserve ordered/deduplicated server semantics.

Pass 2: cover accepted references, invalid/stale references, resource-limited
runtime attribution, history/replay rendering, and reload behavior in browser and
API integration tests.

### Slice 3D — conflict and recovery interaction hardening

Pass 1: add explicit browser flows for stale evidence fingerprint, stale task
revision, capability denial, duplicate submission, and relationship edit conflict.
Show actionable feedback while retaining the last known report.

Pass 2: test reload after each conflict, ensure no duplicate history/event writes,
and verify controls re-enable or remain disabled according to refreshed server
state. Keep authority and lifecycle decisions server-side.

### Slice 3E — closure verification and release evidence

Pass 1: run the complete local suite, browser suite, migration/package checks and
conformance checks against the combined Slice 3 implementation. Resolve any
fixture or cross-slice regressions.

Pass 2: commit the implementation, confirm hosted Quality/browser CI tested that
exact SHA, update maintained documentation in a separate commit, and close the
temporary directive with both SHAs, hosted URL, evidence counts and deferred
limitations.

Acceptance constraints for all five slices:

- Keep each implementation and hardening pass reviewable; do not combine closure
  documentation with implementation changes.
- The server remains authoritative for capability, revision, lifecycle, graph
  bounds and immutable history.
- Preserve unknown-dependence and advisory-readiness language in every UI state.
- Do not add automatic semantic stopping, authenticated multi-operator identity,
  runtime accounting, legacy reconstruction, ambiguous-commit recovery, or
  database privilege/tamper hardening to Slice 3.

## Slice 3A — pass 1: relationship correction, reversal and history (23 September)

The workspace relationship rows now expose server-backed lifecycle actions:

- Directional relationships can be corrected with an explicit new direction and
  reason using the current revision.
- Active relationships can be retracted and eligible latest changes can be
  reversed using the server-provided latest change ID and revision.
- Relationship history can be expanded inline, showing operation, revision and
  reason for each immutable change.
- Symmetric common-origin rows do not expose directional correction controls.
  Server validation remains authoritative for all lifecycle and reversal rules.

Focused browser coverage now exercises directional correction, history rendering,
common-origin creation and retraction. This pass is uncommitted. Remaining 3A
hardening is stale revision/expired reversal conflict feedback and reload
persistence; those are pass 2 before moving to bounded graph visibility.

## Slice 3A — pass 2: conflict and reload hardening (23 September)

Hardened relationship editing with focused browser coverage:

- A stale workspace revision now surfaces the server's investigation-changed
  feedback and leaves the browser dependent on refreshed authoritative state.
- Reload after the conflict preserves the concurrently corrected direction and
  immutable history; history remains inspectable from the refreshed row.
- Existing service coverage already proves reversal-window expiry and stale
  reversal rejection at the API boundary; the browser keeps those errors server-
  rendered rather than attempting local eligibility decisions.

Verification: the stale-revision/reload browser case passed, alongside the
correction/history/common-origin/retraction case. Slice 3A remains uncommitted;
its implementation and hardening are complete for the current UI scope.
Next is Slice 3B bounded graph visibility.

## Slice 3B — pass 1: bounded graph visibility (23 September)

Expanded the workspace source-dependence view with a disclosure panel that shows:

- examined directional and symmetric edges with readable endpoint labels;
- complete versus bounded/truncated status and overflow reason;
- invalid directed-graph warnings;
- omitted frontier source IDs and frontier omission state; and
- explicit language that missing or partial relationships do not establish
  independence.

The relationship browser flow now verifies the bounded graph disclosure and edge
rendering alongside directional correction and symmetric editing. This pass is
uncommitted. Pass 2 will exercise truncated and invalid projections through browser
fixtures and verify that the UI preserves unknown-dependence language in those
states.

## Slice 3B — pass 2: bounded and invalid graph acceptance (23 September)

Added browser fixtures that force the source-dependence projection into bounded and
invalid states. The workspace now has acceptance coverage proving:

- truncated projections display the overflow state and explicitly say remaining
  dependence is unknown;
- invalid directed projections display an invalid-graph warning and prohibit
  treating the view as a valid corroboration structure; and
- the disclosure remains reload-driven and server-authoritative.

The existing relationship flow and the two new graph-state cases pass. Slice 3B
is complete for the current UI scope and remains uncommitted. Next is Slice 3C:
structured source/claim/objective/review and runtime references in the stopping form.

## Slice 3C — pass 1: structured stopping references (23 September)

The stopping form now exposes current report/readiness references:

- source and claim IDs from the report;
- objective indices bound to the latest cycle number;
- current objective-review IDs; and
- operator-supplied runtime-limit evidence lines.

Submission continues to use the readiness task status, revision and evidence
fingerprint. Reference choices are rebuilt only when the report/cycle identity
changes, preserving selections while the operator edits the form. The server still
validates every ID and cycle relationship.

The stopping browser test now selects a current source and objective reference and
verifies accepted submission. This pass is uncommitted. Pass 2 will add claim/review
and resource-limited reference coverage, invalid-reference feedback, and reload /
history assertions.

## Slice 3C — pass 2: runtime attribution and persistence (23 September)

Added browser coverage for a resource-limited stopping decision with a current
source reference and operator-supplied runtime evidence. The accepted decision
renders its resource-limited reason and explicit operator-reported attribution;
after reload, immutable history retains the exact runtime evidence line.

Existing API contract tests continue to reject unknown source, claim, objective,
and review references. Slice 3C is complete for the current UI scope and remains
uncommitted. Next is Slice 3D: explicit browser conflict and recovery interaction
hardening.

## Slice 3D — pass 1: stopping conflict interaction (23 September)

Added browser coverage for a stale stopping readiness basis: evidence is written
through a concurrent client after the workspace loads, submission receives the
server's investigation-changed feedback, and the refreshed report preserves the
legacy unspecified conclusion state without inventing a decision. The form remains
available when the refreshed investigation is still active, allowing a new current
basis to be reviewed.

This is the first 3D pass and remains uncommitted. Remaining 3D hardening covers
relationship conflict feedback in the combined flow, duplicate submission/history
invariants, capability denial presentation, and control-state behavior after each
conflict.

## Slice 3D — pass 2: duplicate/history and conflict invariants (23 September)

Hardened the browser interaction boundary:

- Accepted stopping submission is verified to create exactly one immutable history
  row and one stopping audit event, while the submit control becomes disabled.
- The stale stopping-basis flow confirms conflict feedback, refreshed unspecified
  legacy state, and continued availability for a new current-basis submission.
- Relationship stale-revision conflict/reload coverage from 3A remains green and
  verifies concurrent correction plus history persistence.
- Server integration coverage remains the authority for capability denial and
  reversal-window failures; the workspace displays their refreshed conflict state
  rather than deciding eligibility locally.

The focused stopping acceptance and stale-basis tests passed. Slice 3D is complete
for the current UI scope and remains uncommitted. Next is Slice 3E closure
verification and release evidence.

## Slice 3E — pass 1: combined verification and acceptance audit (23 September)

The combined review supersedes the earlier broad completion claims for 3A–3D.
Focused happy-path tests did not prove all of the planned acceptance criteria.

Corrections made during this pass:

- Relationship editor arrows now respect stored direction instead of always
  displaying low-to-high endpoints.
- An unfinished investigation displays no recorded stopping decision, rather than
  incorrectly describing a legacy conclusion. The server report's legacy fallback
  remains unchanged; workspace display now distinguishes task lifecycle.
- Stopping controls fail closed when readiness/report refresh fails and disable
  when a decision is already accepted. Refreshed stale-evidence submissions are
  checked for no partial writes before a valid follow-up submission.
- Invalidity and truncation are displayed together; missing relationships remain
  explicitly unknown. Missing frontier IDs no longer imply a complete traversal.
- Runtime text is labelled operator-reported and not a verified runtime record.
- Added browser successful-reversal, denied-write/retry, failed-refresh, accurate
  direction, accepted-reference persistence and reload assertions. Removed the
  misleading test that posted resulting_state as if it were an original command.
- Hosted browser count is updated from five to fourteen, still requiring zero
  failures, errors or skipped cases. Formatting/lint issues in accumulated tests
  were corrected.

Acceptance items still open before release (not silently deferred):

1. Retracted relationships disappear from the active traversal projection used by
   the editor. They need a reload-safe discovery/history path to restore or reverse
   retractions. Successful reversal of an active correction is now browser-tested,
   but that does not close this missing lifecycle interaction.
2. Browser actions omit a stable operation ID. Server idempotency tests do not
   prove browser retry after an uncertain response. Add deliberate exact-request
   retention/retry handling before claiming browser-level replay.
3. Direction correction still asks for internal low_to_high/high_to_low values.
   Replace these with named source choices or an explicit swap preview.
4. Complete browser coverage for reversal expiry, edge/depth overflow and omitted
   frontier details, and claim/review selection plus invalid reference feedback.
   The invalid-graph browser fixture stubs the detector; it tests presentation,
   while real persisted-cycle detection is covered by the service suite.
5. Objective/reference selection currently targets only the latest cycle. Confirm
   that restriction or provide an explicit cycle picker before calling all planned
   cycle-qualified reference interactions complete.

Verification results are recorded below when the combined run finishes. This is
the local-verification pass; implementation commit, hosted exact-SHA evidence and
separate maintained-documentation closure remain the release pass. No new commit
or push is made while these acceptance items remain open.

Verification evidence for 3E pass 1:

- Expanded browser suite: 14 passed, zero skipped. Subsequent full run also covered
  the strengthened reference/history reload assertions.
- Full browser-enabled regression run: 1,660 passed, one failed, zero skipped
  (654 warnings). The failure was the previously noted registry-audit assertion
  expecting chronological rows from a SELECT without ORDER BY.
- Corrected that test to verify the exact event multiset, retaining duplicate
  detection without inventing a query ordering contract. The complete registry
  audit suite then passed: 10 tests. The full suite was not repeated after this
  test-only correction; do not describe the earlier run as an all-green full run.
- Ruff, strict mypy (87 source files), final diff whitespace checks, conformance
  traceability, and smoke passed.
- Prototype: fresh 32-migration bootstrap and no-op rerun; real HTTP lifecycle,
  retained cycles and restart/authority-epoch persistence passed.
- Clean wheel: 32 resources matched source checksums; minimal installation,
  populated upgrade, rerun, checksum-drift rejection and application checks passed.
  This wheel check preceded the final UI text/control edits; final-release artifact
  verification must use the final accepted checkout.

Outcome: local verification/audit checkpoint complete, release closure still open.
Carry the five explicit acceptance items above into a corrective pass before 3E
pass 2 (implementation commit, hosted verification and separate docs closure).
All current implementation changes remain uncommitted for review.

## Slice 3E — pass 2: acceptance gaps closed (23 September)

The five corrective items were implemented and exercised locally:

- Current relationship discovery is task-scoped, read-authorized, bounded to 100
  records per page, and includes retracted declarations so history and reversal
  remain available after reload.
- Durable browser writes carry one stable operation ID. The exact serialized
  request is retained in session storage across reload and can be explicitly
  retried after a network failure or uncertain server response. Duplicate history
  and event assertions cover both stopping decisions and relationship writes.
- Direction correction presents the named source endpoints in a swap preview;
  operators no longer enter internal direction enum values.
- Browser coverage now includes reversal expiry, real edge/depth/node overflow,
  omitted frontier behavior, and invalid reference feedback.
- Stopping references can select an earlier objective cycle, including its claim
  and review references; the server rejects unknown references without writing.

Local verification: the browser suite collected and passed 24 cases with zero
failures, errors, or skips. The workflow assertion was raised from 14 to 24.
The implementation and documentation changes remain uncommitted pending review,
hosted exact-SHA verification, and the separate maintained-documentation commit.
