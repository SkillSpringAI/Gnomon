# C3a continuous reconstruction fence: verification and closure

**Status:** **FORMALLY CLOSED** for the bounded C3a reconstruction-fencing slice,
28 September 2026. The implementation SHA is
`0618dec6fb6e0eea2942af2ae9ba672234999882`. Before this documentation-only
closure update, `HEAD`, `origin/main`, and hosted `main` resolved to that SHA and
the working tree was clean. [Quality run 36367975815](https://github.com/SkillSpringAI/Gnomon/actions/runs/36367975815)
completed successfully at that exact SHA. C3b mechanics extraction has not begun.
This closure documentation is separate from the hosted-tested implementation commit.

## Hosted closure evidence

All three required jobs passed at the implementation SHA:

| Job | Result |
|---|---|
| [checks](https://github.com/SkillSpringAI/Gnomon/actions/runs/36367975815/job/108758098598) | Success. Normal regression: **1,886 passed, 28 skipped**; every skip was an intentionally opt-in browser case. Ruff lint, strict mypy, migrations, smoke/prototype, conformance traceability, and database-wheel verification passed. |
| [minimal-install](https://github.com/SkillSpringAI/Gnomon/actions/runs/36367975815/job/108758098743) | Success. Installed base wheel passed without AWS; all **35 migration resources** matched source checksums. |
| [browser](https://github.com/SkillSpringAI/Gnomon/actions/runs/36367975815/job/108758098754) | Success with Chromium: **28 passed**, zero failures, errors, or skips, including the separate JUnit count assertion. |

The checks job applied all **35 migrations**, including
`035_reconstruction_validation_pending.sql`. Its installed-wheel database probe
passed schema installation, populated upgrade, rerun, checksum-drift rejection,
and draft creation. The normal-suite skip report lists only browser tests. Thus
the four real PostgreSQL client-tool cases ran hosted: the two baseline and
restrictive-unresolved `pg_restore` reconstruction variants, the credential-sentinel
`pg_dump`/`pg_restore` case, and the real `pg_dump` backup case. Both real
reconstruction variants call the stronger M2 source/restored equivalence assertion;
the M2 equivalence helper tests were also in the passing normal suite. The hosted
log reports aggregate passing counts rather than individual passed test names.
These M2 checks do not turn bounded production post-restore validation into a
claim of complete semantic equivalence.

## Implemented boundary

Migration 035 adds `security_state.reconstruction_validation_pending BOOLEAN NOT
NULL DEFAULT FALSE`. Existing valid databases upgrade with the value false. The
database constraint requires a pending recovery bootstrap, populated bootstrap
origin, and current version greater than the origin version when validation is
pending; the loader and startup service also reject invalid combinations. Normal
security transitions cannot clear the pending bootstrap, and startup in continuing
or recovery mode preserves the gate.

After manifest/dump validation, pristine-target preflight, and restore-list
planning, reconstruction locks the canonical singleton and commits the validated
manifest state `S`, epoch `E`, origin `S/V`, current version `V+1`, recovery bootstrap
pending, and validation pending. Effective state is `RECOVERY_REQUIRED` before the
data-producing `pg_restore` starts. The former post-import write of unfenced
historical `S/V/E` is removed. Source-pending manifests create a fresh target
bootstrap incident rather than copying unavailable source bootstrap metadata.

Successful selected restore and migrations precede a second singleton-locked
transaction. It checks the expected `S`, `S/V` origin, `V+1`, `E`, both pending
flags, supported PostgreSQL version, migration metadata, critical-table access,
and target database scope, then clears only validation pending. The existing
RecoveryContext service captures a fresh context afterward. These are bounded
production checks, not M2 source/restored semantic equivalence.

The Pass 3A gates reject context capture, including replay, new recovery-bound
operator and execution issuance, protected restoration, and backup publication
while validation is pending. Current-context reads reject pending state;
historical reads and exact authorization replays retain their existing semantics.
The public CLI exposes only full reconstruction into governed recovery.

## Adversarial and restart assessment

Database-backed tests cover all five accepted manifest security states with both
source-pending values. They assert origin `S/V`, current `V+1`, epoch `E`, effective
`RECOVERY_REQUIRED`, and the fresh context's finalized basis. The manifest model
also accepts synthetic pending/non-`RECOVERY_REQUIRED` combinations; the target
still records the manifest's `S/V` as origin and remains effectively fenced. No
manifest schema change was made in C3a.

Failure before the fence commit leaves pristine authority. A failed fence UPDATE
rolls back all manifest authority fields. Interruption after fence commit, after
restore, or during migration/validation leaves both bootstrap and validation
pending. A failed readiness UPDATE also leaves validation pending. Interruption
after publication but before context capture leaves recovery bootstrap pending
and validation false; context capture may be retried on that finalized basis,
but full reconstruction retry remains denied by pristine-target preflight.
After context capture, existing governed recovery owns reconciliation and
restoration. The intended operator response to an incomplete import or validation
remains discard/recreate, not resumable reconstruction. Startup cannot publish
validation readiness.

Tests also reject publication after the target state, version, or epoch changes,
and exercise context capture and authorization issuance against the publication
lock and backup publication against the pre-import fence. A contender either
rejects while pending or proceeds against the committed finalized basis. Archive
`security_state` data remains excluded from restore. No supported path installs
historical authority unfenced after import.

The private `_publish_reconstruction_readiness()` has one production call site,
after successful restore and migration in `_restore_verified_data()`. Its
successful-import evidence is the enclosing trusted control flow, not a durable
database marker; direct invocation by privileged internal code is not a supported
operator path. This is acceptable for C3a's existing internal trust model. **C3b
constraint:** mechanics extraction must not expose publication independently or
permit callers to bypass successful import, migration, and bounded validation.
`require_current_execution()` retains its existing read semantics; it has no
production point-of-effect caller in this slice and was intentionally not made a
general permission gate. Historical authorization alone does not satisfy the
pending gate on protected restoration.

## Local verification

- Focused reconstruction, security, recovery, authorization, backup, and migration
  suites: **1,381 passed, 4 skipped**. The four skips require local `pg_dump` or
  `pg_restore` executables.
- Normal full suite: **1,882 passed, 32 skipped**. The skips include 28 opt-in
  browser cases and the four PostgreSQL-client cases.
- Ruff lint, strict mypy, `git diff --check`, migration
  upgrade/default/idempotency tests, local migration
  rerun, smoke, prototype, and conformance traceability checks passed.
- Clean base wheel and disposable-database wheel checks passed. The packaged wheel
  carried 35 matching migration resources; its database check passed fresh
  install, populated upgrade, rerun, historical-drift rejection, and API draft.
- The real PostgreSQL reconstruction/equivalence drill was **not run locally**:
  neither `pg_dump` nor `pg_restore` is installed. Simulated runner tests are not
  equivalent evidence. The hosted run above exercised both real reconstruction
  variants and the credential-sentinel and dump cases at the exact C3a SHA.
- Browser regression is recorded separately from the normal suite. The initial
  concurrent local run had 26 passes and two source-registry fixture 403 errors
  while another security suite used the same database. The isolated rerun passed
  **all 28 browser cases** with zero skips or errors.

Repository-wide pre-existing Ruff formatting debt is outside C3a. A scoped
full-file formatter check passed during Pass 3C, then the final pre-commit
hygiene pass removed unrelated formatter churn from existing lines in C3a-touched
files. Ruff lint and `git diff --check` pass on the resulting implementation diff;
no full-file formatting claim is made for that baseline formatting. The
implementation was committed and hosted-verified at the SHA recorded above. This
documentation-only closure does not include production, test, or C3b changes.
