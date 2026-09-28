# M3a — Runtime and owner database credential closure

**Status:** Formally closed for the bounded runtime/operator credential-selection
slice. Production implementation:
`78a9e408887559e5e100a6f4d22376afee799522`. Hosted
[Quality run 36382958751](https://github.com/SkillSpringAI/Gnomon/actions/runs/36382958751)
tested that exact SHA and passed `checks`, `minimal-install`, and `browser`.
This documentation-only closure follows the tested implementation; M3b has not
begun.

`DATABASE_URL` remains the ordinary API/runtime connection. Migration, backup,
and complete reconstruction operator commands require `OWNER_DATABASE_URL`,
without fallback to the runtime URL. Their owner engines are command-scoped.
The [credential procedure](../operations/database-credentials.md) records the
deployment grants and upgrade order. Code-level URL selection does not itself
create distinct PostgreSQL roles in a deployment.

The hosted normal suite reported **1,908 passed, 28 browser-only skips**. No
PostgreSQL-client or role test was skipped. Both real `pg_dump`/`pg_restore`
reconstruction variants (`baseline` and `restrictive_unresolved`) ran through
their C3a/M2 source/restored equivalence assertions. Real PostgreSQL role tests
created separate owner and runtime principals, checked `current_user` on both
configured connections, exercised permitted runtime work and denied runtime
DDL/migration-ledger access, and verified owner migration and backup selection.
The separate Chromium suite reported **28 passed, zero skipped**.

All **35 migrations** applied. Fresh installation, populated upgrade, rerun,
historical-drift rejection, and the installed-wheel database probe passed. The
separate `minimal-install` job passed its clean base-wheel check, including all
35 packaged migration checksums and operation without AWS dependencies.

The hosted log showed no unexpected credential exposure, runtime-URL fallback,
or environment-dependent failure. The configured owner URL was masked in the
migration log. PostgreSQL permission errors in service logs were the expected
negative privilege tests. Correctly provisioning distinct deployed credentials
remains an operator responsibility; identical URLs would not constitute role
separation. M3a does not protect mutable rows or audit history against the
privileged owner/administrator. M3b and later M3 persistence work remain open.
