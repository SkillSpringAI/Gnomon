# Database migrations

The first schema is in [`001_initial.sql`](001_initial.sql). It stores investigation briefs and plans as JSONB while keeping research cycles and audit events queryable as separate records. Evidence and provenance tables are in [`002_evidence.sql`](002_evidence.sql). The controlled source registry is in [`003_trusted_sources.sql`](003_trusted_sources.sql). Hypothesis assessments are in [`004_hypothesis_assessments.sql`](004_hypothesis_assessments.sql).

The initial service does not require a database connection to expose its health endpoint or run unit tests. The PostgreSQL service is available through `docker compose` for integration work.

Migration `005_cycle_planning_basis.sql` adds a JSONB planning-basis list to research cycles. Existing rows default to an empty list; apply it before starting the evidence-aware planner. No rows are rewritten by application code or removed.

Migration `006_cycle_outcomes.sql` adds cycle start/completion timestamps, a bounded
result summary, evidence and claim ID lists, and unresolved objectives. Existing cycles
remain `planned` with empty outcome fields. The migration is additive and repeatable.

Migration `008_attempted_objectives.sql` adds the durable list of objectives explicitly
attempted by a runner or operator outcome. Existing cycles default to an empty list. The
migration is additive and repeatable.

Migration `009_objective_results.sql` adds per-objective source/claim associations as
JSONB. Existing cycles default to an empty list, preserving unknown historical mappings.
It is additive and repeatable; apply it before running the updated application.

Migration `010_objective_reviews.sql` adds append-only operator review history to each
cycle as JSONB. Existing rows receive an empty list. Apply it before starting the updated
application. Review history and its audit event are committed in one transaction.

Migration `011_cycle_progress_tracking.sql` adds a durable-progress marker and recovery
reason. Existing cycles default to untracked with no recovery reason. This does not
reconstruct missing historical mappings. New runner acquisitions enable tracking;
source/claim associations reuse the cycle's existing progress fields.

Migration `012_persistence_invariants.sql` adds database checks for non-negative
historical predecessor versions, positive journal versions, and the governed operation
set. The migration runner records a SHA-256 checksum for every applied migration and
fails closed if an applied file is modified.

Migration `013_restrict_audit_task_deletion.sql` changes the audit-event task foreign key
to `ON DELETE RESTRICT`. Tasks with retained audit events must be archived or logically
deleted through a future governed lifecycle operation; physical deletion is rejected.

Migration `014_task_archive_status.sql` adds `archived` as a terminal task lifecycle
state. It can be reached from concluded or abandoned investigations through the existing
compare-and-set status endpoint and preserves all retained history.

Migration `015_cycle_attempts.sql` adds durable cycle execution identities and stage/status
fields for crash recovery and operator inspection.

Migration `016_report_generation_attempts.sql` adds atomic, idempotent provider-budget
reservations for report drafting.

Migration `017_report_attempt_expiry.sql` adds reservation expiry timestamps so abandoned
pending provider attempts can be marked `EXPIRED` and safely recover capacity.

Migration `018_cycle_attempt_artifacts.sql` records source and claim identities on the
durable cycle attempt as those artifacts are committed.

Migration `019_provider_attempt_dispatched.sql` adds a non-expirable dispatched
state so in-flight provider work is not refunded by reservation expiry.

Migration `020_provider_attempt_unknown.sql` adds conservative recovery for
provider outcomes that cannot be established after dispatch.

Migration `021_security_state.sql` adds the singleton versioned operational
security state and seeds a normal state for new installations.

Migration `020_provider_attempt_unknown.sql` adds `UNKNOWN` for unresolved remote
outcomes. It retains capacity, has no terminal timestamp, and may accept a late
known result. Existing attempt rows and their recorded history are unchanged.

The canonical SQL files are now in `src/research_agent/migrations/` and ship as
Python package resources. This directory retains migration documentation only.
The move preserves original filenames and byte-for-byte checksums. Never edit an
applied migration: add a new numbered SQL resource. Missing or empty resource
directories fail explicitly, including in installed wheels.

The application expects all numbered migrations to be present. Run
`python -m research_agent.cli migrate` (or `make migrate`) after PostgreSQL is ready.
The runner creates `research_agent_schema_migrations`, takes a transaction-scoped
PostgreSQL advisory lock, applies pending files in filename order, and records each
completed filename. Tracking-table bootstrap also holds the advisory lock so two
fresh installers cannot race its creation. Each migration runs in its own transaction; a failure rolls back
that migration and stops the command. The numbered SQL remains additive and repeatable.
