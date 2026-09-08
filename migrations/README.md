# Database migrations

The first schema is in [`001_initial.sql`](001_initial.sql). It stores investigation briefs and plans as JSONB while keeping research cycles and audit events queryable as separate records. Evidence and provenance tables are in [`002_evidence.sql`](002_evidence.sql). The controlled source registry is in [`003_trusted_sources.sql`](003_trusted_sources.sql). Hypothesis assessments are in [`004_hypothesis_assessments.sql`](004_hypothesis_assessments.sql).

The initial service does not require a database connection to expose its health endpoint or run unit tests. The PostgreSQL service is available through `docker compose` for integration work.

Migration `005_cycle_planning_basis.sql` adds a JSONB planning-basis list to research cycles. Existing rows default to an empty list; apply it before starting the evidence-aware planner. No rows are rewritten by application code or removed.

The application currently expects migration 005 to be present. The SQL is additive and
repeatable, but there is no migration-version table or automatic runner yet. Applying
the scripts in filename order to a fresh database creates the complete local schema.
