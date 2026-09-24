# Baseline restoration — 24 September 2026

Implementation commit: `ef11f70a53d44bdfa41ad1a4d14d5d523fd27623`.

The previous Slice 3 commit (`11c46ae`) passed hosted browser and minimal-install
jobs but failed normal pytest setup: the listing tests registered another test
module as a plugin instead of exposing the fixture directly. The correction uses
an explicit fixture import and lookup and has passed both standalone invocation
and collection with the complete suite.

The same corrective commit preserves an uncertain browser request when a replay
receives a rejection. Rejection of a later attempt cannot establish whether the
original operation committed. Further writes remain paused and the original
operation ID and payload survive reload until authorized retry confirms the result.
Four added browser cases exercise denied replay for stopping and relationship
writes, both before and after the original operation commits. They assert identical
payloads and one accepted history entry; stopping also checks one audit event.

Local checks completed against the corrective implementation:

- Eight focused retry cases and two standalone listing cases passed.
- Ruff, strict mypy (87 files), conformance traceability and smoke passed.
- Fresh database: 32 migrations; rerun made no changes. Real HTTP and restart
  persistence, including authority epoch, passed.
- Clean wheel: 32 resources matched source checksums; minimal installation,
  populated upgrade, rerun, checksum-drift rejection and application probes passed.

Full local regression passed: 1,677 tests, zero skipped, 689 warnings in 325 seconds,
with browser tests enabled. The redirected output was delayed; the completed log
confirmed success. An unnecessary diagnostic rerun was stopped after retrieving
that result and is not counted as verification evidence.

Hosted [Quality run 35937991144](https://github.com/SkillSpringAI/Gnomon/actions/runs/35937991144)
verified the exact implementation SHA above: `checks`, `minimal-install` and
`browser` all passed. Ordinary pytest passed 1,649 tests with the expected 28
opt-in browser skips; the separate browser job passed all 28 with zero skips.
Hosted smoke, prototype, conformance and database-wheel steps passed too.
Milestone 0's implementation verification gate is closed.

The following documentation-only commit records this evidence and the maintained
roadmap. Its SHA is available from the Git history of this record; it does not
replace the implementation SHA tested by this run.

## Boundaries retained

Browser pending state is scoped to session storage in the current tab. Closing the
tab or clearing storage requires inspecting server history to reconcile outcomes.
A rejected replay remains unresolved; this pass adds no abandon or automatic repair
operation. Current authorization still applies to every server retry. Runtime-limit
references remain operator-reported. Privileged database tampering, role separation,
authenticated operator identity and full recovery authority retain their roadmap
boundaries. No recovery or architectural expansion is included in this correction.
