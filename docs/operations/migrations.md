# Database Migrations

The canonical numbered SQL migrations are packaged under [`src/research_agent/migrations`](../../src/research_agent/migrations). The repository-level [`migrations/README.md`](../../migrations/README.md) records the migration history and operational rules.

Run `python -m research_agent.cli migrate` (or `make migrate`) after PostgreSQL is ready. The runner applies pending files in filename order, records checksums, uses a transaction-scoped advisory lock, and stops on failure. Never edit an applied migration; add a new numbered SQL resource.

Migration verification is part of the integration and packaging checks. The application expects all numbered resources to be present, including in installed wheels.
