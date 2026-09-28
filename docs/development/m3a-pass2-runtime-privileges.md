# M3a Pass 2 — PostgreSQL runtime privilege characterization

Baseline: C3 closure `e70b337bc5a8dddc80e819cc92a8aa33aa9e19d6`, with
the uncommitted M3 Pass 1 record preserved. This pass changes no production
code, credential configuration, or deployment grants.

## Candidate role and real-database evidence

`tests/integration/test_runtime_database_privileges.py` creates a disposable
PostgreSQL 16 database with separate login roles. The database owner is **not**
superuser; the runtime role owns no application table and is a member of no
owner role. The fixture revokes inherited `PUBLIC` database/schema privileges,
so the runtime login has no database `TEMP` or `CREATE` by ambient grant. The
owner applies migrations 001–034, inserts a task, applies 035,
and reruns the full chain without changes. `pgcrypto` is installed. The admin
credential that creates/drops the disposable roles and database is fixture
setup authority, not runtime authority.

The candidate *normal-runtime* grants, over the current 35-migration schema,
are:

- Database `CONNECT`; schema `public` `USAGE`.
- `SELECT` on all 25 application tables (every `public` table except
  `research_agent_schema_migrations`). This is the bounded table-level candidate
  rather than an assertion that every table is read by every runtime path.
- `INSERT` on all 24 application tables other than singleton `security_state`.
- `UPDATE` on `research_tasks`, `research_cycles`, `research_claims`,
  `hypothesis_assessments`, `trusted_sources`, `research_cycle_attempts`,
  `report_generation_attempts`, `security_state`, and `source_relationships`.
- `DELETE` only on `claim_sources` and `assessment_evidence`, the two governed
  memory-link replacement paths.
- No sequence privilege: migration inventory has no serial/identity/`nextval`
  object, the disposable schema has zero sequences, and runtime can call
  `gen_random_uuid()`.

The explicit table/grant inventory test fails when a new migration adds a table
without review. This is a table-level candidate, not a column-minimal proof.
The actual service test exercises task insert/status update, source/claim and
assessment writes, both link DELETE/reinsert paths, task/security row locks,
recovery bootstrap and context capture, operator and execution issuance, and
same-transaction event/context/authorization audit inserts. DML paths for
provider, trust and stopping records are represented by the grant inventory,
not separately executed as service tests in this pass; their grants require
review if those paths evolve.

The restricted login receives SQLSTATE `42501` for `CREATE TABLE`, `ALTER
TABLE`, `DROP TABLE`, `CREATE SCHEMA`, `ALTER SCHEMA`, `CREATE EXTENSION hstore`,
and `run_migrations()`. It has neither database nor schema `CREATE`. The
current no-op migration invocation still executes `CREATE TABLE IF NOT EXISTS`
and `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` on the ledger, so migration
authority cannot be inferred from the absence of pending SQL files.

## Owner delta, backup, and reconstruction

The migration owner needs database `CONNECT` and `CREATE` (fresh `pgcrypto`
installation), `public` schema `USAGE` and `CREATE`, ownership/ALTER authority
for existing schema objects and the migration ledger, and ledger
`SELECT`/`INSERT`/`UPDATE`. The disposable database owner has those through
ownership, without superuser. See PostgreSQL 16's [trusted extension](https://www.postgresql.org/docs/16/pgcrypto.html)
and [privilege](https://www.postgresql.org/docs/16/ddl-priv.html) rules.

Normal runtime does not need ledger `SELECT`, but the supported backup
inspection does. The real `pg_dump` probe succeeds with a SELECT-capable role,
yet a strictly read-only login fails backup *publication* at its final
`security_state FOR SHARE` lock: PostgreSQL requires UPDATE privilege on at
least one column even for `FOR SHARE` ([PostgreSQL 16 SELECT](https://www.postgresql.org/docs/16/sql-select.html)).
The test then grants ledger `SELECT` to the restricted runtime login; the
complete real `pg_dump` plus manifest publication succeeds with that additive
read grant. It uses the host `pg_dump` when available or the same PostgreSQL
container's `pg_dump` through Docker locally. This does **not** justify adding
a dedicated production backup credential now. A future strictly read-only
backup role would need a publication-lock design change, not just more grants.

Current reconstruction is one `DatabaseReconstructionService.reconstruct()`
operation. Its engine/URL supplies SQL preflight and final S/V/E fence updates,
the `pg_restore --data-only --single-transaction` subprocess credentials,
post-import `run_migrations()`, bounded validation/readiness publication, then
recovery bootstrap and context capture. Even if data import uses only data
write rights, the current **same credential** needs migration ownership for
the guarded sequence. A future credential boundary would have to preserve the
single private fenced operation while giving its migration step an owner
connection; it must not expose migration, readiness publication or recovery
entry as separate public workflows. No reconstruction credential split is
implemented here.

## Security and next slice

Runtime/owner separation would block runtime SQL from changing schema or
installing extensions. It would **not** stop a compromised runtime credential
from directly changing rows in tables where its legitimate DML grants apply,
including canonical `security_state`, nor from inserting or (where granted)
modifying application data outside service-level checks. Audit history is
append-only by application convention and grants, not cryptographically
immutable; an owner/admin can alter it. The absence of runtime DELETE on audit
tables reduces one mutation path but is not administrator-level tamper
resistance.

The smallest next production slice is deployment role/grant provisioning plus
a runtime DSN that has only these grants, retaining a distinct owner credential
for `migrate` and the **complete** reconstruction operation until its internal
credential transition can be designed. `DATABASE_URL` is currently shared by
API, migration, backup and restore, so a configuration/entrypoint change is
required; this pass deliberately does not make it. A single runtime credential
can also run the existing backup if granted ledger `SELECT`. M3a remains a
viable first M3 slice, with the reconstruction credential handoff as an
explicit design constraint rather than an independent restore mode.
