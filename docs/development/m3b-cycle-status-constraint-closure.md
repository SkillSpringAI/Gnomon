# M3b Pass 2 — Research-cycle status constraint closure

**Status:** Formally closed for the selected cycle-status value invariant.
Production implementation: `5038f6f2414c357359e314d2a220932ffcade6bb`.
Hosted [Quality run 36511325666](https://github.com/SkillSpringAI/Gnomon/actions/runs/36511325666)
tested that exact SHA and passed `checks`, `minimal-install`, and `browser`.
At verification, `HEAD == origin/main` at the implementation SHA and the working
tree was clean. This documentation-only closure follows the tested implementation.

Migration `036_research_cycles_status_valid.sql` adds the named
`research_cycles_status_valid` check for `planned`, `active`, `completed`,
`blocked`, and `failed`. It preserves the existing `NOT NULL` contract and does
not encode lifecycle transitions. Invalid deployed legacy rows fail the
transactional migration without a 036 ledger entry or automatic coercion; the
[operator audit query](../operations/migrations.md) supports investigation
before upgrade. The constraint is deliberately not translated into an ordinary
persistence category. Other [Pass 1 candidates](m3b-pass1-material-persistence-invariants.md)
remain deferred.

The hosted normal suite reported **1,914 passed, 28 browser-only skips**. There
were no PostgreSQL-client-tool or restricted-role skips. The real
`test_real_pg_restore_rejects_legacy_invalid_cycle_status` executed: an
incompatible pre-036 backup was rejected by the target constraint while the
C3a reconstruction fence remained validation-pending. Both existing real
`pg_restore` reconstruction variants (`baseline` and `restrictive_unresolved`)
also executed and retained their C3a/M2 equivalence assertions. Real M3a role
tests exercised distinct configured owner/runtime principals and the restricted
runtime privilege boundary. The separate Chromium suite reported **28 passed,
zero skipped**.

Hosted migration installation applied all **36 migrations**, including 036, to
a fresh database. Integration tests covered valid populated upgrade, all five
accepted statuses, exact-name rejection of an unsupported value, and an invalid
legacy row aborting upgrade while the prior ledger and row remained unchanged.
The fresh prototype rerun was a no-op. The installed database wheel contained
all 36 migration resources with matching source checksums and passed populated
upgrade, rerun, historical-drift rejection, and installed CLI migration. The
separate `minimal-install` job passed its base-wheel check without AWS
dependencies. This is bounded PostgreSQL test-deployment evidence, not a claim
that every deployed database has valid historical rows.
