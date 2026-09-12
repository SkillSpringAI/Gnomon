# Database migrations

The first schema is in [`001_initial.sql`](001_initial.sql). It stores investigation briefs and plans as JSONB while keeping research cycles and audit events queryable as separate records. Evidence and provenance tables are in [`002_evidence.sql`](002_evidence.sql). The controlled source registry is in [`003_trusted_sources.sql`](003_trusted_sources.sql). Hypothesis assessments are in [`004_hypothesis_assessments.sql`](004_hypothesis_assessments.sql).

The initial service does not require a database connection to expose its health endpoint or run unit tests. The PostgreSQL service is available through `docker compose` for integration work.

Migration `005_cycle_planning_basis.sql` adds a JSONB planning-basis list to research cycles. Existing rows default to an empty list; apply it before starting the evidence-aware planner. No rows are rewritten by application code or removed.

Migration `006_cycle_outcomes.sql` adds cycle start/completion timestamps, a bounded
result summary, evidence and claim ID lists, and unresolved objectives. Existing cycles
remain `planned` with empty outcome fields. The migration is additive and repeatable.

The application expects all numbered migrations to be present. Run
`python -m research_agent.cli migrate` (or `make migrate`) after PostgreSQL is ready.
The runner creates `research_agent_schema_migrations`, takes a transaction-scoped
PostgreSQL advisory lock, applies pending files in filename order, and records each
completed filename. Each migration runs in its own transaction; a failure rolls back
that migration and stops the command. The numbered SQL remains additive and repeatable.
