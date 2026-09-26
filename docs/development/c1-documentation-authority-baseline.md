# C1 Documentation Authority and Architectural Invariant Baseline — Completion Record

**Date:** 26 September 2026.

**Scope:** Documentation and authority baseline only.

**Implementation HEAD reviewed and locally tested:** `6be538ed6b32107c0ba69dacb73e8c057d55386b`.

**Working tree at the initial completion report:** Uncommitted C1 documentation changes; 48 changed paths, all under `docs/`, including this record. No C1 commit or hosted run was claimed at that checkpoint.

**Last hosted-green implementation:** `93e383eb0acf8ba2a389d888c45023355b0ff7af`, [Quality run 36108631071](https://github.com/SkillSpringAI/Gnomon/actions/runs/36108631071), covering `checks`, `minimal-install`, and `browser`, with 1,819 passed and 28 skipped in the main suite. That run predates C1.

## Outcome

The maintained documents now distinguish current truth, future work, normative rules, execution records, verification evidence, and history. INV-01–INV-12 and the transaction vocabulary are established without changing runtime behavior. Useful historical records and their original limitations remain available.

The documentation objective is fulfilled and locally verified within the limits below. Commit and hosted verification remain pending; this record does not assert the roadmap's committed-and-hosted slice closure gate or release conformance. C2 has not begun.

## Files changed

Paths below are relative to the repository root. The moved roadmap is listed at both its former and retained destination paths so the deletion is not mistaken for loss of evidence.

| File | Reason |
|---|---|
| `docs/README.md` | Clarify document lifecycle and authority ownership. |
| `docs/architecture/agent-runtime.md` | Constrain M5 wording to shared vocabulary and narrow primitives. |
| `docs/architecture/external-agent-network.md` | Scope older network-state words historically and retain scoped containment as future work. |
| `docs/architecture/overview.md` | Establish INV-01–INV-12 and link their verification map. |
| `docs/architecture/persistence.md` | Record ATOMIC, FENCED, STAGED, and FAILURE-EVIDENCE; correct M2's supported status. |
| `docs/archive/README.md` | Clarify preservation and historical authority rules. |
| `docs/archive/superseded-plans/GNOMON_SOURCE_OF_TRUTH.md` | Repair a local reference after archive relocation. |
| `docs/archive/superseded-plans/known-gaps.md` | Repair a local reference after archive relocation. |
| `docs/conformance/authority-matrix.md` | Mark classifications as dated section-level traceability, not blanket current behavioral proof. |
| `docs/conformance/implementation-status.md` | Replace the chronological journal with current verification scope and limits; link C1 evidence. |
| `docs/development/Gnomon Dependency-Ordered Development Roadmap.md` | Move the superseded dated plan to the archive; the maintained `roadmap.md` owns future work. |
| `docs/development/M2 Incremental Implementation Sequence.md` | Mark its historical execution role; distinguish completed M2.1–M2.11 from remaining instructions. |
| `docs/development/authority-epoch-replacement.md` | Mark the completion record as dated evidence rather than current authority. |
| `docs/development/authority-foundations.md` | Mark the completion record as dated evidence rather than current authority. |
| `docs/development/authorization.md` | Mark the completion record as dated evidence rather than current authority. |
| `docs/development/backup-creation.md` | Mark the completion record as dated evidence rather than current authority. |
| `docs/development/backup-manifest.md` | Mark the completion record as dated evidence rather than current authority. |
| `docs/development/backup-state-inspection.md` | Mark the completion record as dated evidence rather than current authority. |
| `docs/development/canonical-reconstruction-fixture.md` | Mark the completion record as dated evidence rather than current authority. |
| `docs/development/conformance.md` | Distinguish regression, milestone, and release verification; constrain the traceability script's claim. |
| `docs/development/credential-sentinel-verification.md` | Mark the completion record as dated evidence rather than current authority. |
| `docs/development/cycle-closure-authority.md` | Mark dated evidence and repair its implementation-status link. |
| `docs/development/database-reconstruction.md` | Mark the completion record as dated evidence rather than current authority. |
| `docs/development/development-history.md` | Retain concise M0/M1/M2 closure narratives, archived detail, and C1 provenance. |
| `docs/development/m1-authorization-pre-m1.6-gap-register.md` | Mark its dated gap register so it cannot override later completion evidence. |
| `docs/development/reconstruction-epoch-rotation.md` | Mark the completion record as dated evidence rather than current authority. |
| `docs/development/reconstruction-equivalence-verifier.md` | Mark the completion record as dated evidence rather than current authority. |
| `docs/development/reconstruction-reconciliation-restoration.md` | Mark the completion record as dated evidence rather than current authority. |
| `docs/development/recovery-bootstrap-boundary.md` | Mark the completion record as dated evidence rather than current authority. |
| `docs/development/recovery-context.md` | Mark the completion record as dated evidence rather than current authority. |
| `docs/development/recovery-reconciliation.md` | Mark the completion record as dated evidence rather than current authority. |
| `docs/development/recovery-restoration.md` | Mark the completion record as dated evidence rather than current authority. |
| `docs/development/restore-preflight.md` | Mark the completion record as dated evidence rather than current authority. |
| `docs/development/restore-to-recovery.md` | Mark the completion record as dated evidence rather than current authority. |
| `docs/development/roadmap.md` | Collapse completed detail to closure references; reconcile M2, the six-part M4 programme, and M5's bounded scope. |
| `docs/development/source-of-truth.md` | Establish concise current implementation, hosted baseline, guarantees, material gaps, and supporting references. |
| `docs/governance/memory-authority.md` | Recognize the supported M2 drill while retaining procedure, authentication, and deployment limits. |
| `docs/governance/research-methodology.md` | Recognize the hosted M2 drill without claiming broader release readiness. |
| `docs/governance/security-authority.md` | Reconcile state vocabulary, AuthorityDirection, separate recovery dimensions, restoration asymmetry, and M2 status. |
| `docs/source_of_truth/Gnomon Repository Cleanup Working Plan.md` | Mark the old cleanup plan as historical. |
| `docs/source_of_truth/Slice 13 Security State Model and Transition Table.md` | Preserve the implementation record while directing current authority to maintained governance. |
| `docs/source_of_truth/repository-documentation-inventory.md` | Mark the old inventory as historical. |
| `docs/archive/completed-slices/2026-09-26-pre-c1-implementation-status-journal.md` | Preserve the former status journal, exact evidence, failures, and checkpoint limits; rebase links. |
| `docs/archive/completed-slices/2026-09-26-pre-c1-source-of-truth-journal.md` | Preserve the former chronological current-state document and original M2.7 checkpoint evidence; rebase links. |
| `docs/archive/superseded-plans/2026-09-26-pre-c1-roadmap-detail.md` | Preserve the former completed M0/M1 instructions and detailed planning evidence; rebase links. |
| `docs/archive/superseded-plans/Gnomon Dependency-Ordered Development Roadmap 2026-09-23.md` | Retain the moved dated roadmap with an explicit historical banner and corrected links. |
| `docs/conformance/architectural-invariant-verification.md` | Map existing tests and their limits to each invariant without inventing coverage. |
| `docs/development/c1-documentation-authority-baseline.md` | Record the required C1 completion report, local commands, host limits, and pending hosted gate. |

## Authority reconciliation

| Role | Maintained owner |
|---|---|
| Current truth | [Current source of truth](source-of-truth.md): implementation baseline, guarantees, limits, and material gaps. |
| Future work | [Roadmap](roadmap.md): remaining dependency order, scope, exit gates, and deferrals. |
| Normative architecture/governance | [Architecture overview](../architecture/overview.md), [persistence](../architecture/persistence.md), [security authority](../governance/security-authority.md), and the other maintained architecture/governance documents. |
| Verification evidence | [Implementation status](../conformance/implementation-status.md) summarizes current scope; the [invariant map](../conformance/architectural-invariant-verification.md), dated completion records, and exact hosted runs identify evidence. The [matrix](../conformance/authority-matrix.md) owns requirement traceability. |
| Historical implementation detail | [Development history](development-history.md), dated records, and [archive](../archive/README.md). Original failures and superseded checkpoint claims are retained with their dates. |
| Execution contracts | Active bounded directives/slice plans; historical completed plans are not permanent architectural authority. |

The development source-of-truth path is the maintained current-truth document; older similarly named source material is historical. Regression Quality, bounded milestone verification, and stronger release conformance remain distinct. `check_conformance.py` validates authority revision/matrix traceability; it does not prove behavior or release conformance.

## Invariants

The [register](../architecture/overview.md#architectural-invariants) establishes all twelve IDs. The [verification map](../conformance/architectural-invariant-verification.md) identifies exact existing test files and refactoring implications.

| ID | Established rule | Evidence classification |
|---|---|---|
| INV-01 | Governed mutation is fail-closed. | Bounded executable evidence. |
| INV-02 | Durable authority precedes consequential external dispatch. | Bounded executable evidence. |
| INV-03 | Governing locks/transactions are released across external work. | Bounded executable evidence; no universal lock-duration test. |
| INV-04 | Governed state and required audit commit atomically. | Bounded executable evidence. |
| INV-05 | Execution authority belongs to the exact durable attempt. | Bounded executable evidence. |
| INV-06 | Operator recovery is bound to observed-state freshness. | Executable stale-fingerprint evidence. |
| INV-07 | Restoration requires its dedicated authority path. | Bounded executable evidence. |
| INV-08 | Security state, bootstrap, epoch, attempt, and fingerprint remain separate. | Combined bounded evidence; no single taxonomy test. |
| INV-09 | Specified governed history remains append-only. | Partial executable evidence; privileged-owner tampering excluded. |
| INV-10 | Source/provider/agent execution remains explicit. | Design/structure invariant; no specific executable prohibition of generic runners. |
| INV-11 | Durable infrastructure requirements are explicit. | No direct invariant-specific executable evidence identified. |
| INV-12 | Reconstruction does not manufacture operational trust. | Bounded executable evidence; real restores depend on PostgreSQL client tools. |

Transaction vocabulary records existing correctness requirements: ATOMIC commits state and required evidence together; FENCED commits reservation before external effect and reconciles later; STAGED leaves commit/rollback to the caller; FAILURE-EVIDENCE can persist designed bounded failure evidence after failed work rolls back. It introduces no global Unit of Work.

## Security reconciliation

- `NORMAL`, `DEGRADED`, `COMPROMISED_SUSPECTED`, `LOCKDOWN`, and `RECOVERY_REQUIRED` remain the five persisted global states. Suspected compromise remains distinct from degradation; lockdown remains explicit global restriction.
- `SAFE` is not restored as an enum value. Its useful meaning is expressed through explicit safe capabilities in restrictive states.
- `ISOLATED` remains future scoped containment for bounded components, separate from the global enum; no implemented scoped-isolation claim is made.
- `RECOVERY_REQUIRED` grants no recovery authority by itself. Recovery actions require separate authorization.
- Recovery bootstrap is the separate reconstructed-authority trust fence. SecurityState, AuthorityEpoch, RecoveryContext/evidence, execution attempt identity, and the operator recovery fingerprint retain separate purposes.
- AuthorityEpoch identifies authority lineage/version; it is not a security-state synonym. Restoration from reconstructed authority preserves protected recovery and fresh epoch handling.
- AuthorityDirection's `REDUCE`, `PRESERVE`, and `BROADEN` participate in structural legality, actor/reason authorization, administration/recovery capabilities, and persisted version checks. They are not a complete permissiveness ordering of restricted states.
- Recovery from reconstructed/restored authority is not an ordinary security-state transition. No enum, transition, or capability code changed.

## M2/M4/M5 reconciliation

**M2:** Functionally established for the supported PostgreSQL test deployment, with bounded consolidation remaining. Shared recovery reads/inventory, separation of restore mechanics from governed entry, useful restore-list planning extraction, lifecycle cleanup, and preservation of reconstruction/recovery tests remain. Bootstrap, epoch replacement, protected restoration, and deterministic reconciliation are not reopened as redesigns. Broader operator procedure and deployment/release evidence remain open.

**M4:** The confirmed programme consists of documentation/invariants, recovery shared reads, reconstruction mechanics, investigation/execution ownership, repository/read projections, and invariant verification mapping. File size alone does not justify decomposition. Cohesive security-critical services remain intact when a split would obscure authority or atomicity.

**M5:** Shared vocabulary covers attempt identity, authority/epoch where applicable, deadlines, budgets, point-of-effect revalidation, unknown outcomes, interruption, and reconciliation. Only justified narrow lifecycle primitives are contemplated. One generic CycleRunner, one workflow engine, and erasure of path-specific orchestration are explicitly excluded.

## Verification

Local environment: Windows, Python 3.12.10, PostgreSQL 16 in the project's Docker container. Hosted Quality uses Ubuntu/Python 3.11; local results are practical equivalents with the differences recorded here. Docker Desktop was initially stopped, then started with `docker desktop start`; the existing project PostgreSQL container became healthy.

| Exact command/check | Result |
|---|---|
| `python -m ruff check .` | Exit 0, all checks passed. |
| `python -m mypy src` | Exit 0, no issues in 101 source files. |
| `python scripts/check_conformance.py` | Exit 0, pinned hashes, Documents 01–07 coverage, and evidence references passed. Traceability only. |
| `python -m research_agent.cli migrate` | Exit 0, 0 migrations applied; none pending. |
| `python -m pytest -ra` | Exit 0, 1,815 passed, 32 skipped, 634 warnings, 240.95 seconds. |
| `python scripts/smoke_test.py` | Exit 0, prototype smoke test passed. |
| `python scripts/verify_prototype.py` | Exit 0, 34 fresh migrations applied and rerun was a no-op; real HTTP lifecycle, two cycles, blocked outcome, and restart/epoch persistence passed; disposable database removed. |
| `python scripts/verify_wheel.py` | Exit 0, clean base installation, dependency check, 34 packaged migration checksums, memory API, and provider status passed without AWS. |
| `python scripts/verify_wheel.py --database` | Exit 0, base probes plus disposable database schema, upgrade, rerun, drift rejection, and draft checks passed; disposable database removed. |
| PowerShell: `$env:RUN_BROWSER_TESTS='1'; $env:PLAYWRIGHT_CHANNEL='msedge'; python -m pytest tests/integration/test_workspace_browser.py -ra -x -q` | Exit 0, all 28 browser tests passed, none skipped. |
| `python -m pytest tests/integration/test_workspace_browser.py --collect-only -q` | Exit 0, confirmed 28 browser cases. |
| `git diff --check` | Exit 0, no whitespace errors. |
| `git diff --name-only -- src tests scripts migrations .github pyproject.toml` | Empty output. |
| `git diff --unified=0 -- tests` | Empty output; no skip marker or test-behavior changes. |
| `git -c core.quotePath=false status --short` and changed-path audit | All changed and untracked paths are under `docs/`. |

### Local link check

The following Python body was executed through PowerShell's `$code` here-string and `python -c $code`. It verifies inline Markdown local file targets, not anchor correctness or external availability. Step 15 reported 67 Markdown files and zero missing local targets; the final rerun after adding this report and its references passed with 68 Markdown files and zero missing local targets.

```python
from pathlib import Path
from urllib.parse import unquote
import re
root = Path("docs")
missing = []
for file in root.rglob("*.md"):
    content = file.read_text(encoding="utf-8")
    for target in re.findall(r"(?<!!)\[[^\]]*\]\(([^)]+)\)", content):
        target = target.split(" ", 1)[0].strip("<>")
        target = unquote(target.split("#", 1)[0].split("?", 1)[0])
        if not target or "://" in target or target.startswith(("mailto:", "data:")):
            continue
        if not (file.parent / target).exists():
            missing.append(f"{file}: {target}")
print(f"Markdown files: {len(list(root.rglob('*.md')))}; missing local links: {len(missing)}")
for item in missing[:30]:
    print(item)
raise SystemExit(bool(missing))
```

### Attempts and limits retained

- The first normal-suite attempt and a diagnostic `python -m pytest -ra -vv --maxfail=1` attempt were interrupted while PostgreSQL was unavailable; the diagnostic interruption identified `psycopg.connection`. Neither is recorded as a passing test run. The successful full run followed database startup.
- Of the 32 normal-suite skips, 28 are the existing opt-in browser cases and were subsequently executed successfully. Four existing backup/reconstruction cases skip because host `pg_dump`/`pg_restore` are absent. No skips were introduced by C1. These four tool-dependent cases were not locally exercised; the prior hosted-green run exercised them.
- With `RUN_BROWSER_TESTS=1` and `PLAYWRIGHT_CHANNEL=chromium`, `python -m pytest tests/integration/test_workspace_browser.py -ra` produced 28 setup errors: Windows could not spawn the installed Chromium binary (`spawn UNKNOWN`). An elevated retry with `-ra -x -q` reproduced the launcher error. Edge is the successful local browser equivalent; the CI Chromium job has not been rerun for C1.
- Warnings include existing FastAPI lifecycle deprecations and dependency warnings. C1 made no code changes to address them.
- Final report/link additions received traceability, local-link, whitespace, and changed-path checks. Runtime tests were not repeated for those Markdown-only additions.

## Runtime diff check

No runtime service, SQLAlchemy model, schema, migration, security enum, transition policy, capability policy, script, CI/configuration, or test-behavior file changed. Tracked and untracked changed paths are documentation only. There are no newly added test skips or weakened tests. No generic Unit of Work/CycleRunner, scoped isolation, M5 implementation, service/repository split, or fresh-agent handoff was introduced.

## Remaining conflicts and limits

No unresolved documentation-versus-executable-behavior contradiction requiring runtime changes was identified during C1. Older security words, chronological checkpoint status, and superseded plans remain visible as historical evidence with current ownership made explicit.

The authority matrix still contains section-level partial/conflicting classifications and release gaps; C1 does not convert those into satisfied behavioral claims. INV-10 remains a design invariant and INV-11 lacks direct invariant-specific evidence. Broader deployment/release obligations remain as listed in current truth and the roadmap. The local PostgreSQL-client and Chromium launch limitations above are verification limits, not reconciled away.

## Recommended C2 prerequisites

Only prerequisites surfaced by C1 are identified here:

1. Define the bounded recovery shared-read/inventory contract from the current RecoveryContext and reconciliation consumers, including freshness, supported inventory, and fail-closed missing/contradictory evidence.
2. Identify the durable infrastructure requirements and composition owner explicitly (INV-11); do not imply that a broad persistence port can satisfy a PostgreSQL-dependent authority contract without declaring that dependency.
3. Name transaction/lock ownership before extraction and preserve separate security state, bootstrap, epoch, context/evidence, attempt, and fingerprint dimensions.
4. Carry forward the mapped reconstruction, restrictive-outcome, audit rollback, freshness, late-result, protected-restoration, and epoch tests relevant to the extracted boundary; specify any actual coverage gap rather than inventing existing evidence.
5. Preserve the separation between reconstruction mechanics and governed recovery entry; do not broaden the read-boundary slice into recovery redesign or generic orchestration.

These are planning prerequisites only. No C2 implementation has begun.
