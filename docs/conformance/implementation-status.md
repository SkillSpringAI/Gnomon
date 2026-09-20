# Gnomon implementation status

## Implementation status updated on 2026-09-20

Latest verified commit: `4ea2693d368eee016b6f0436a0366faf17922c5d`.
[Hosted Quality run #14](https://github.com/SkillSpringAI/Gnomon/actions/runs/35418622604)
succeeded for this exact commit. Both checks and minimal-install jobs passed,
covering lint, strict typing, migrations, tests, smoke, prototype, conformance,
and clean-wheel verification (including PostgreSQL in the checks job).

Point-of-effect enforcement is implemented for READ_AUDIT on audit and security
transition history, source retrieval, and provider dispatch. Canonical runtime
security states and capability policy are implemented; this does not establish
full restoration or recovery authority. Authority Epoch and actor/reason hardening
are implemented in the verified checkpoint described below. Recovery/bootstrap
machinery remains unimplemented.
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

**Implemented locally; closure pending.** The [temporary gap checklist](../temporary-docs/2026-09-20-slice-closure-gaps.md)
tracks final-tree verification, runner failure propagation, preservation coverage,
transaction composition and hosted checkpoint evidence. Passing tests below do not
close those outstanding gates. Base is `4ea2693`; no new hosted result is claimed. The
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

Broad regression: **1,244 passed, 5 skipped** (opt-in browser checks). Ruff and
strict mypy pass (79 source files). Clean-wheel validation passes, including all
23 migration resources, populated upgrade, rerun and checksum drift rejection.
No schema migration was needed: the closure event uses the existing JSON audit
payload. Existing FastAPI deprecation and intermittent Pydantic alias warnings
remain. A final missing-row guard was added to the locking helper after broad
verification; the final focused closure/ordering suite passes **30 tests**, and
smoke plus real HTTP lifecycle/restart verification both pass with that guard.

Contracts #1–#5 remain unchanged. No recovery/bootstrap, epoch replacement,
protected restoration, generic containment mutation API, or external-call
cancellation was added. The development memory backend and unrelated/direct ORM
writers are outside the PostgreSQL commit-ordering claim. Interim checkpoint:
`checkpoint-2026-09-20-review-closure-gaps-before-continuing`. This checkpoint
preserves work in progress; it does not close the slices or their remaining gates.

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
