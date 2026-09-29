# Database Migrations

The canonical numbered SQL migrations are packaged under [`src/research_agent/migrations`](../../src/research_agent/migrations). The repository-level [`migrations/README.md`](../../migrations/README.md) records the migration history and operational rules.

Run `python -m research_agent.cli migrate` (or `make migrate`) after PostgreSQL is ready. The runner applies pending files in filename order, records checksums, uses a transaction-scoped advisory lock, and stops on failure. Never edit an applied migration; add a new numbered SQL resource.

Migration verification is part of the integration and packaging checks. The application expects all numbered resources to be present, including in installed wheels.

Migration 036 adds the named `research_cycles_status_valid` check. Before an
upgrade, an operator can inspect the target database with:

```sql
SELECT status, count(*)
FROM research_cycles
WHERE status NOT IN ('planned', 'active', 'completed', 'blocked', 'failed')
GROUP BY status
ORDER BY status;
```

The existing `status` column is `NOT NULL`; migration 036 does not change its
nullability. Invalid historical values make the migration fail and leave its
ledger entry unapplied. Investigate the data and its provenance before retrying;
the migration does not rewrite, delete, or map unknown statuses. The check
protects only the stored vocabulary. Legal lifecycle transitions and concurrency
remain enforced by application services and transactions.
