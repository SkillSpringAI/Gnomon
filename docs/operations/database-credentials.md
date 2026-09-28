# PostgreSQL runtime and owner credentials

`DATABASE_URL` is the ordinary API/runtime connection. Set it to a dedicated
non-owner login in a hardened deployment. The process-global engine and
`SessionFactory` use only this URL. The repository's default local URL and
Docker Compose bootstrap user remain development conveniences and are **not** a
restricted production runtime role.

`OWNER_DATABASE_URL` is required by `python -m research_agent.cli migrate`,
`scripts/backup_postgres.py`, and `scripts/restore_postgres.py`. It names a
PostgreSQL psycopg database owner/migration login. Those commands create and
dispose an owner engine; they never fall back to `DATABASE_URL`. The owner URL
must be supplied only to the short-lived operator process. Do not inject it
into the API/worker environment or mount an `.env` containing it there: a
compromised runtime process can read any secret made available to that process,
regardless of which Python module loads it. The two URLs must point to the same
intended database when operating on one deployment, but use different roles.

The current backup command also uses the owner URL. Backup inspection reads the
migration ledger, and final publication takes `security_state FOR SHARE`, which
requires UPDATE privilege on at least one column in PostgreSQL. A pure SELECT
role cannot complete that workflow. The runtime role deliberately has no ledger
access, so using the owner command credential avoids broadening runtime grants.
This is an operator-process exposure, not a claim that backup itself needs DDL.

## Provisioning order

1. Under an administrator/owner connection, create a separate runtime login.
   Ensure it is neither the database/schema/table owner nor a member of an owner
   role. Review inherited `PUBLIC` grants; the role must not receive database
   `CREATE`/`TEMP` or schema `CREATE` through them.
2. Run all migrations with `OWNER_DATABASE_URL` set only for that command.
   Fresh installation needs database `CREATE` for trusted `pgcrypto`, schema
   `CREATE`, and ownership of the migration ledger and evolving objects.
   Populated upgrades and no-op reruns need ledger ownership/ALTER authority.
3. Apply the current table-level grants below using the owner. Substitute the
   actual database and role names; these examples use `research_agent` and
   `research_agent_runtime`. Review the list after **every new migration**.
4. Set `DATABASE_URL` to the restricted login in the API/worker environment,
   without `OWNER_DATABASE_URL`. Verify `current_user` and the negative
   `has_database_privilege`/`has_schema_privilege` checks before serving traffic.

```sql
-- On a dedicated database, remove ambient creation/temporary authority.
SET search_path = public;
REVOKE CREATE, TEMP ON DATABASE research_agent FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE research_agent TO research_agent_runtime;
GRANT USAGE ON SCHEMA public TO research_agent_runtime;

GRANT SELECT ON TABLE
  research_tasks, research_cycles, research_events, research_sources,
  research_claims, claim_sources, trusted_sources, hypothesis_assessments,
  assessment_evidence, memory_changes, research_cycle_attempts,
  report_generation_attempts, security_state, security_state_transitions,
  trusted_source_policy_events, provider_session_events, source_relationships,
  source_relationship_changes, stopping_decisions, stopping_decision_changes,
  recovery_contexts, recovery_context_audit, operator_authorizations,
  execution_authorizations, authorization_audit
TO research_agent_runtime;

GRANT INSERT ON TABLE
  research_tasks, research_cycles, research_events, research_sources,
  research_claims, claim_sources, trusted_sources, hypothesis_assessments,
  assessment_evidence, memory_changes, research_cycle_attempts,
  report_generation_attempts, security_state_transitions,
  trusted_source_policy_events, provider_session_events, source_relationships,
  source_relationship_changes, stopping_decisions, stopping_decision_changes,
  recovery_contexts, recovery_context_audit, operator_authorizations,
  execution_authorizations, authorization_audit
TO research_agent_runtime;

GRANT UPDATE ON TABLE
  research_tasks, research_cycles, research_claims, hypothesis_assessments,
  trusted_sources, research_cycle_attempts, report_generation_attempts,
  security_state, source_relationships
TO research_agent_runtime;

GRANT DELETE ON TABLE claim_sources, assessment_evidence
TO research_agent_runtime;
```

No normal-runtime grant is needed on `research_agent_schema_migrations` or on
sequences in the current schema. Do not use `GRANT ... ON ALL TABLES` or
`ALTER DEFAULT PRIVILEGES` to admit future tables without review. PostgreSQL
row locks, including `FOR SHARE`, require UPDATE privilege on at least one
column of the locked table. The [M3a Pass 2 role test](../development/m3a-pass2-runtime-privileges.md)
proves the grant set against disposable owner/runtime logins and documents the
backup exception.

For an existing deployment, first identify the actual owner of the database,
schema, tables and migration ledger. Merely setting a new owner URL does not
transfer ownership; a different login without those rights will fail migrations
and reconstruction. Run migrations and grant review before switching the API
URL. Existing installations using the same superuser for everything remain
functional only as a local/development configuration and do not gain privilege
separation from this code change alone.

The complete reconstruction operator workflow uses the owner URL for preflight,
the S/V/E fence, `pg_restore`, migrations, readiness publication, and governed
recovery entry. Do not split or invoke these phases independently. A failed
reconstruction still requires discarding and recreating its target.

This separation denies schema management to a correctly provisioned runtime
role; it does not stop that role from directly changing rows covered by its
legitimate DML grants. The owner/administrator can change schema and retained
audit rows. Application append-only audit behavior is not cryptographic or
administrator-level tamper resistance.
