# Gnomon implementation status

## Implementation status updated on 2026-09-23

Latest implementation baseline: `995f9cc9d0683cdbf331ec4f3708492d7b4231a4` (`995f9cc`).
Hosted [Quality run 35806845915](https://github.com/SkillSpringAI/Gnomon/actions/runs/35806845915) tested this exact SHA;
`checks`, `minimal-install`, and `browser` all passed. This evidence covers the
implementation commit, not the subsequent documentation-only closure commit.

## Source-dependence contract closure (23 September 2026)

Slice 1 of the 22 September sequence is closed within supported application paths.
Migration 030 persists versioned canonical commands. Exact authorized retries
return the historical accepted result; old rows without original command metadata
remain readable but replay is refused. History reads validate chain continuity,
identity and current-head agreement without repair.

Task SHARE locks stabilize graph reads against supported task-UPDATE writers.
Traversal has shared node/edge/depth limits, bounded frontier output and explicit
omission/invalidity. Examined directed cycles are reported; partial views never
establish global acyclicity or independence. Review fingerprints preserve broad
invalidation while unrelated evidence does not reopen complete narrow reviews.
PostgreSQL tests cover reciprocal writes, both lockdown orders and overflow rollback.

Recorded final implementation-local evidence: 1,620 passed, zero skipped with
browser enabled; lint, strict mypy (87 source files), conformance traceability,
smoke, real HTTP restart and clean-wheel checks passed. All 30 migration resources
were verified with fresh/populated upgrade, rerun and checksum-drift checks. Hosted
Quality independently passed the exact SHA above, including the existing five
browser cases. Those cases do not prove the new Slice 3 interactions.

History is appended by supported application operations, not protected against
privileged database rewriting. The inspected local identity is a superuser/table
owner. Least-privilege role separation returns at deployment privilege hardening;
cryptographic tamper evidence returns at the audit-assurance milestone. Legacy
command backfill requires a trusted reconstruction source and a real compatibility
need. Graph repair requires a separately governed recovery design. Dense-graph
performance profiling is due before high-volume use; bounded fetched rows are not
a guarantee of bounded physical database work. Direct SQL writers are outside the
lock-protocol guarantee.

A source-registry audit ordering assertion failed once during an earlier local
full run and passed standalone and on the full rerun. Retain this flake as a known
verification risk, not as proof of a source-dependence defect or a reason to erase
the failed result. Stopping correctness and workspace interactions remain open.

Point-of-effect enforcement is implemented for READ_AUDIT on audit and security
transition history, source retrieval, and provider dispatch. Canonical runtime
security states and capability policy are implemented; this does not establish
full restoration or recovery authority. Authority Epoch and actor/reason hardening
are implemented in the verified checkpoint described below. Recovery/bootstrap
is implemented only for the restrictive entry boundary; reconciliation and
restoration completion remain unimplemented.
Contracts #1–#5 remain untouched. The lifecycle-closure authority question is
tracked in [source of truth](../development/source-of-truth.md#known-implementation-question).

Gnomon currently implements a local research API with PostgreSQL tasks, bounded
cycles, manual lifecycle/outcome control, approved HTTP source retrieval, exact
evidence deduplication, conservative claim extraction, provenance links, current
hypothesis assessments, snapshots, deterministic reports and optional provider drafts.
Claims and hypothesis assessments now use governed versioned memory, reversible
changes, and expanded redacted audit events. Agent-network research remains
limited to a read-only domain contract, deterministic adversarial fake, persisted
agent-message evidence, derived report comparisons, and a local bounded cycle runner;
live platform adapters and long-running orchestration remain absent.

## Bounded source-dependence baseline (21 September 2026)

**Implemented and hosted-verified.** Migration 028 adds canonical task-scoped
`derived_from` and `common_origin` relationships with active/retracted lifecycle,
application-appended change history, optimistic revisions, baseline operation retry, atomic
redacted audit, and source-ownership constraints. API adapters expose create,
read, mutation, reversal, history, and bounded projection operations.

Reports, rule-based drafts, planner inputs, and the credential-free workspace
expose declared relationships and bounded limitations. Missing, partial, or
truncated dependence remains unknown; the implementation does not infer causal
independence, increase confidence, upgrade claim status, or treat repeated
sources as independent evidence.

Local focused contract coverage is 11 tests; consumer-focused coverage is 29
tests. Fresh migration/restart, wheel, conformance, and browser checks pass.
The full local suite reached 1,570 passed and 5 skipped on the changed tree;
one unrelated unordered policy-event concurrency assertion failed once and
passed in isolation. Hosted Quality run 35554268153 passed the exact baseline
SHA across checks, minimal-install, and browser.

Deferred limitations are invalid persisted-graph recovery, causal/transitive
source inference, automatic independence evaluation, broad source discovery,
and authenticated multi-operator identity. This section preserves the historical
21 September baseline; later provider and source-dependence closure is recorded separately.

“Phase 1–4 foundation” accurately describes the repository. “Phases 1–4 complete”
does not: entity models, raw-source storage, cross-task retrieval, general claim
revision rules and semantic evaluation remain absent or partial.

## Local authority foundation slices (19 September 2026)

A synchronizes the baseline and dependency order. B adds migration 023, validated
AuthorityEpochId, canonical epoch persistence, `(epoch, version)` identity, new
transition audit binding, and API visibility. Historical transitions remain
unbound; no replacement epoch or execution-authorization binding is implemented.
C adds an explicit state/actor/reason matrix and capability-direction classification.
See [authority foundations](../development/authority-foundations.md) for exact
semantics, accepted reasons, and deferred restoration questions.

B verification before C: **355 passed, 5 skipped** (opt-in browser checks), Ruff,
strict mypy, conformance, smoke, fresh 23-migration bootstrap/rerun, real HTTP
restart with epoch persistence, and clean-wheel populated upgrade/drift checks pass.
The adversarial checks cover null/nil/malformed lineage, missing canonical state,
repeat migration, retained history, and denial without a capability grant.
C focused verification: **869 passed**, including all 825 state/actor/reason
combinations, 25 direction pairs, invalid actor/reason values, and transition/API
integration. Hosted Quality runs #13 and #14 subsequently passed for the checkpoint.

Final regression after refinements: **1,214 passed, 5 skipped** (opt-in browser
checks). This includes the no-op response race regression and two cached-session
regressions. Capability reads and locked transition reads now refresh existing
ORM objects, preventing stale NORMAL state or versions from surviving a concurrent
lockdown. No-op responses retain the identity observed before releasing the lock.

Ruff, strict mypy (78 source files), conformance, and diff checks pass. Clean-wheel
verification was rerun against the final runtime changes: all 23 migration resources,
populated upgrade, idempotent rerun, drift rejection, and draft checks pass. Real
HTTP lifecycle/restart verification also passes with stable epoch identity.
Existing FastAPI deprecation and intermittent Pydantic alias warnings remain.
Checkpoint: `checkpoint-2026-09-19-authority-foundations`. The test counts above
are local results. Hosted runs #13 and #14 both succeeded for `4ea2693`, with both
checks and minimal-install jobs successful (confirmed 20 September).

## Interruption closure and mutation ordering (20 September 2026)

**Closed.** The [archived gap checklist](../archive/completed-slices/2026-09-20-slice-closure-gaps.md)
records final-tree verification, runner failure propagation, preservation coverage,
transaction composition and hosted checkpoint evidence. The implementation base was
`4ea2693`; the closing checkpoint is
`checkpoint-2026-09-20-interruption-ordering-closed`. The
[closure/locking record](../development/cycle-closure-authority.md) documents the
lock order before implementation and the exact bounded mutation fields.

- Source and agent runners use an internal exact-attempt closure operation. It
  retains committed evidence, claims and objective progress, sets BLOCKED/INTERRUPTED,
  and appends one accurately attributed audit with attempt and observed epoch/version.
- Matching repeats are idempotent. Foreign attempts, caller mismatches and unrelated
  terminal outcomes conflict. Audit failure rolls back the entire closure; missing
  or invalid authority never manufactures success.
- General outcome writes and memory reversal enforce MEMORY_MUTATION.
- Memory stage/reverse, source creation, general outcomes and bounded closure share
  task FOR UPDATE → security FOR SHARE → dependent rows → audit ordering. Security
  transitions acquire security FOR UPDATE only. Locks persist to commit/rollback.
- PostgreSQL tests observe actual row blocking through pg_blocking_pids for both
  race orders of all five paths. Ordinary mutation denies when lockdown wins;
  bounded containment closure remains permitted and records current authority.
- Both runners propagate missing authority, injected invalid-authority loading and
  closure-audit failure after committed progress. They make no later adapter call,
  manufacture no BLOCKED/INTERRUPTED state, and retain the unresolved cycle/attempt.
- Full snapshots with nonempty evidence, claims, objective results, reviews,
  provenance, memory history and attempt artifacts prove closure changes only its
  documented fields. Closure succeeds in all four restrictive states.
- The complete production `MemoryService.stage()` inventory is same-task. Multiple
  stages commit under one outer transaction and later-stage failure rolls the batch
  back. Cross-task batching is unsupported and is not required by a supported caller.

Final broad regression: **1,256 passed, 5 skipped** (opt-in browser checks). Ruff and
strict mypy pass (79 source files). Clean-wheel validation passes, including all
23 migration resources, populated upgrade, rerun and checksum drift rejection.
No schema migration was needed: the closure event uses the existing JSON audit
payload. Existing FastAPI deprecation and intermittent Pydantic alias warnings
remain. The final focused closure/ordering suite passes **42 tests**. Ruff, strict
mypy, conformance, smoke, real HTTP lifecycle/restart, and both clean-wheel modes
pass on the same tree. Hosted Quality checks and minimal-install also pass for the
exact tagged closing commit.

Contracts #1–#5 remain unchanged. No recovery/bootstrap, epoch replacement,
protected restoration, generic containment mutation API, or external-call
cancellation was added. The development memory backend and unrelated/direct ORM
writers are outside the PostgreSQL commit-ordering claim. The earlier
`checkpoint-2026-09-20-review-closure-gaps-before-continuing` remains an interim,
open-gaps checkpoint and is not reused as closure evidence.

## Capability-policy hardening v2 (20 September 2026)

**Implemented.** `AUTHORITY_ADMINISTRATION` is canonical and direction-aware rather
than always safe. `SECURITY_CONTAINMENT` permits only REDUCE/PRESERVE effects and
cannot broaden authority. `RECOVERY_ACTION` permits only PRESERVE-purpose work in a
restrictive state; it grants no ordinary execution/mutation and cannot authorize an
authority change by itself. Security-state modification separately requires
`AUTHORITY_ADMINISTRATION` for the actual effect direction, so recovery intent never
replaces actual-effect authority.

Trusted-source registration and activation are the current authority-bearing
configuration writers. They require PRESERVE and BROADEN administration respectively;
their security SHARE lock is held through commit so a restrictive transition cannot
race an activation through on stale authority.

Unknown, invalid and omitted directions fail closed for all three directional
capabilities. The exhaustive unit matrix covers every current
state × capability × direction tuple plus unknown/omitted negative cases. Transition
integration proves that permitted recovery purpose still fails when administration
is denied, while the existing structural and actor/reason matrix remains intact.
No OperatorAuthorization, protected restoration, RecoveryContext, new state, or
broad authorization refactor was introduced. Slice regression: **1,503 passed,
5 skipped** (opt-in browser checks); Ruff, strict mypy (79 source files), and
conformance pass.

## Recovery/bootstrap entry boundary (20 September 2026)

**Implemented for entry only.** `AUTHORITY_STARTUP_MODE` distinguishes pristine
fresh deployment, ordinary continuation and recovery bootstrap. Continuing startup
does not change state, version or epoch. Recovery startup takes the canonical row
lock before request handling, records a durable pending fence plus restored origin,
advances the version once, retains the epoch and exposes effective
RECOVERY_REQUIRED. Repeated recovery startup and later continuing restart preserve
that restrictive identity.

While pending, only safe read/audit/report/diagnostic capabilities remain. Ordinary
mutation/dispatch, directional authority capabilities and normal security transitions
deny. An adversarial restored-state test includes raw NORMAL, trusted enabled
configuration, a RUNNING attempt, evidence/claim provenance and a PENDING provider
reservation; it proves no provider/source/agent dispatch, no START_CYCLE, no ordinary
memory mutation and no historical authorization consumption before reconciliation.

Migration 024 persists and constrains the fence. There is intentionally no clearing
or reconciliation operation, RecoveryContext, protected restoration, external
recovery, backup tooling, OperatorAuthorization or epoch-replacement API. See the
[entry-boundary record](../development/recovery-bootstrap-boundary.md).

Final bounded-scope regression: **1,512 passed, 5 skipped** (opt-in browser tests).
Ruff and strict mypy pass across 80 source files; conformance, smoke, real HTTP
restart, fresh/upgrade/rerun/drift verification for all 24 migrations, and both
clean-wheel modes pass on the final tree.

## Failed-cycle observability and persistence error boundaries (20 September 2026)

Slices 2 and 3 are locally complete in the current working tree. Failed bounded
cycles expose one task-scoped, read-only latest-attempt projection containing
durable stage/status, timestamps, recovery reason, retained evidence and claims,
attempted/unresolved objectives, and active-cycle truth. The workspace loads that
projection on refresh and after reload without performing recovery or mutation.

Recognized PostgreSQL constraint failures now use a bounded translator based on
structured driver diagnostics. Trusted-source duplicates, provider operation
duplicates, and reviewed security invariants receive stable internal categories;
unknown or undiagnosed failures remain unexpected. Public security-invariant
responses are generic and do not expose SQL or constraint details.

Local closing-tree verification: **1542 passed, 5 skipped** in the default suite;
the opt-in browser suite passed **5 tests**. Ruff, strict mypy across 82 source
files, conformance, smoke, disposable PostgreSQL prototype/restart verification,
fresh/upgrade/rerun/drift migration checks, and clean-wheel verification passed.
The default skips are only the opt-in browser tests. This local evidence is not a
hosted release or v0.1 conformance claim.

## Verification synchronization and hosted browser coverage (21 September 2026)

Priority 1 adds a required `browser` job to the Quality workflow. It uses the
PostgreSQL service, installs the `[dev,browser]` extra and Chromium with Linux
dependencies, sets `RUN_BROWSER_TESTS=1` and `PLAYWRIGHT_CHANNEL=chromium`,
applies migrations, and runs the workspace browser suite. When enabled, missing
Playwright or a browser launch failure is a hard failure rather than a silent
skip. The browser tests bridge requests to the in-process test application; they
do not establish live external services or a deployed browser-to-server stack.

Implementation evidence for this follow-up is the committed baseline `4157917`
and hosted run `35548463523`. The hosted browser gate recorded **5 browser tests
passed with zero skips, failures, or errors** through the JUnit gate. The final
local default suite recorded **1,559 passed and 5 skipped**.
The browser cases used an installed Windows Chrome executable because this host
cannot spawn Playwright's downloaded Chromium; hosted CI remains pinned to its
downloaded Ubuntu Chromium installation.

## Legacy governed-memory history compatibility (21 September 2026)

Migration 007 assigned pre-existing claims and hypothesis assessments version one
without an original journal row. The first governed mutation may therefore be
the supported `(previous_version=1, version=2)` shape when its non-null
`previous_state` validates as the version-one baseline. Historical reads expose
that baseline without inventing an actor, timestamp, or change ID; new targets
retain the ordinary version-one `CREATE` row.

History validation now rejects targets with no journal, missing intermediate
versions, mismatched prior state, malformed state, invalid target types, and
unsupported starting shapes as stable conflicts. Reads remain side-effect free.
Focused PostgreSQL integration evidence: **15 passed**, including both claim and
assessment upgrade shapes, baseline reconstruction, no-journal behavior,
missing-intermediate rejection, malformed-state rejection, and unchanged journal
rows after reads. No migration resource changed for this memory slice. Final
regression and hosted verification are recorded in the closure section below.

## Trusted-source policy audit (21 September 2026)

Trusted-source registration and activation now stage redacted configuration-scoped
events in the same transaction as the registry write. Events retain only the
registry ID, operation, old/new status, trusted local-operator context, observed
authority epoch/version, bounded result/reason, and event time. Duplicate
registration remains a conflict without a second event; repeated enable is an
explicit `no_op`, not a new authority expansion. Audit persistence failure rolls
back the registry change.

The audit read endpoint enforces `READ_AUDIT` at the service boundary and does
not expose domains, source prose, verification text, URLs, secrets, raw request
data, or SQL diagnostics. PostgreSQL interleaving tests cover activation-before-
lockdown and lockdown-before-activation orders. Focused evidence: **10 passed**
for atomicity, rollback, redaction, capability enforcement, duplicate/repeat
semantics, actor validation, and both race orders. Coverage is limited to these
two registry operations. Provider-session creation/deletion now also has a
separate redacted lifecycle event table and `READ_AUDIT` endpoint; authenticated
multi-user identity and unrelated configuration writers remain open.

Provider-session lifecycle evidence (21 September 2026) records only provider,
credential mode, bounded TTL, trusted local-operator context, authority
epoch/version, result/reason, and event time. Bearer tokens, cookies/session
identifiers, and provider diagnostics are never persisted. Creation requires
authority broadening; deletion requires authority reduction. The in-memory
development backend remains intentionally non-durable and returns an empty
audit collection. Replacement of an active session emits deletion evidence
before the new creation evidence without persisting either session's secret or
identifier. Focused provider-session evidence is **8 PostgreSQL integration
tests plus 8 provider unit tests**, including stage/commit rollback,
expiry/capacity rollback, replacement/delete races, two-replacement races,
redaction, and authority reads.

## Evidence-bound stopping decisions (21 September 2026)

**Implemented and hosted-verified.** Migration 029 adds a monotonic task revision,
current stopping-decision projection, immutable decision history, four structured
reasons, bounded evidence references, readiness/fingerprint checks, and atomic
conclusion with redacted audit. Exact retries are idempotent; stale, conflicting,
active-attempt, capability, audit, and concurrent transition cases are rejected
without partial state.

Reports and the credential-free workspace expose the persisted reason, rationale,
limitations, and stale evidence basis. Legacy direct `CONCLUDED` transitions remain
compatible and report `unspecified` rather than fabricated sufficiency. Automatic
semantic stopping, automatic reopening, authenticated multi-operator identity,
and distributed PostgreSQL/process-memory crash atomicity remain deferred.

Focused stopping/workspace coverage is **18 tests**, and the populated migration
upgrade fixture verifies pre-007 claim and assessment records through current HEAD.

## Historical checks (15 September 2026)

Slice 12B local verification: **296 passed, 5 skipped** (opt-in browser tests),
with two Pydantic alias warnings in concurrency tests. Ruff and strict mypy pass.
All 20 packaged migrations apply to a fresh database and rerun idempotently.
Clean-wheel verification passes outside the checkout, without AWS dependencies,
including concurrent bootstrap, populated upgrade and checksum-drift rejection.
Smoke, real HTTP lifecycle/restart, and authority traceability checks pass.
The table below preserves the earlier baseline's check results; current hosted
evidence is recorded above.

| Command | Result |
| --- | --- |
| `python -m pytest -ra` | 255 passed, 5 skipped; includes PostgreSQL integration suites and governance, recovery, audit, provider-budget, and boundary tests |
| `python -m ruff check .` | All checks passed |
| `python -m mypy src` | Success; 72 source files |
| `python scripts/check_conformance.py` | Source hashes, all 395 Documents 01–07 section groups, and evidence references pass |
| Traceability negative checks on temporary copies | Missing section, invalid evidence reference, and changed source revision correctly rejected |
| Final `python -m ruff check .` / `python -m mypy src` | Pass; 72 source files checked by mypy |
| `git diff --check` | Pass |

These results establish the historical regression baseline, not missing capability
coverage. No live Bedrock or Moltbook call, deployment penetration test, or recovery
drill was performed. Existing tests use isolated database records and controlled
provider/network substitutes where applicable.

The matrix classifies entire source sections, including subordinate requirements;
it does not claim a separate behavioral test for every normative sentence. Mixed
sections remain partial or conflicting, with implementation evidence and limitations.
Slice 1 now answers what exists and what is missing without treating design prose as
code. Slices 2–5 have executable evidence; no v0.1 conformance is claimed.

## Today's ordered implementation gates

| Order | Slice / deliverable | Baseline readiness |
| --- | --- | --- |
| 1 | Repository baseline and authority conformance | 395 section groups across Documents 01–07 mapped to code/tests/gaps; complete replacement Document 08 reviewed |
| 2 | Memory proposal and deterministic validation | Implemented for claims and hypothesis assessments; proposal, validation, commit, journal, lifecycle API and actor boundary are present |
| 3 | Versioned state | Implemented for claims and hypothesis assessments with optimistic versions and append-only journal |
| 4 | 48-hour rollback | Implemented with duplicate, stale, concurrent, dependent, expired and conflict tests |
| 5 | Audit expansion | Implemented for task creation/mutation, cycles, sources, claims, assessments via governed memory events, rollback, and redacted payload metadata; security event type is available for boundary integrations |
| 6 | Security boundary tests | HTTP policy remains bounded; shared untrusted-text, data-delimiting, and capability guards now have deterministic adversarial tests; broader agent/tool boundaries remain future work |
| 7 | Agent domain model | Partial: neutral identity, question, and observation objects implemented; live network persistence and platform lifecycle remain absent |
| 8 | Fake/adversarial network | Partial: bounded deterministic fake, persisted agent-message evidence, comparison, audit, and local cycle integration are implemented; live adapters remain absent |
| 9 | Moltbook adapter | Not implemented; depends on fake-network gate |
| 10 | Research-loop integration | Local fake-agent acquisition is connected to one bounded cycle runner; long-running and live acquisition remain absent |
| 11 | Persistent execution attempts and recovery | Implemented; atomic startup, operator closure before attachment, interrupted processes and late evidence are covered for bounded runners |
| 12 | Provider budget and concurrency governance | Slices 12A/12B complete for the reviewed scope: lifecycle closure, clean-wheel resources, configured memory lifetime, provider settings/limits and public reason categories; remaining broader gaps are in the canonical ledger |
| 13 | Conformance/release gate | Not satisfied |

## Gate evidence required before v0.1 candidate

1. Maintain the mapped authority sections and split requirement groups as features
   are implemented. Expand Document 08's supplemental findings into requirement/test
   mappings during security implementation; its complete source is now available.
2. Prove the initial five memory operations use deterministic validation, trusted
   actor attribution, atomic state/history/audit writes and optimistic concurrency.
3. Prove normal, duplicate, stale, concurrent, dependent, expired and conflicting
   rollback behavior with immutable original history and new rollback events.
4. Enumerate all knowledge/security writers and verify event coverage, redaction
   and failure behavior. Protect history from ordinary deletion paths.
5. Exercise hostile external inputs, capability denial, malformed responses,
   leakage, replay, timeouts and resource limits across the actual adapters.
6. Integrate fake-agent observations as evidence through the existing investigation
   without granting external actors mutation authority; only then add platform integration.
7. Record security, epistemic and recovery review outcomes against the matrix.

See [authority-matrix.md](authority-matrix.md) for requirement evidence and
[archived known-gaps](../archive/superseded-plans/known-gaps.md) for historical implementation risks and decisions.
