# Credential Sentinel Verification — M2.11

Date: 25 September 2026.
Status: local command test passed; real PostgreSQL drill awaiting hosted Quality.

The real PostgreSQL drill populates the canonical reconstruction fixture, then
sets fake AWS access-key, secret-key, session-token and Bedrock bearer sentinels.
It sends a separate fake bearer token through the provider-session HTTP route
and checks that the token remains in the process-memory session store while
the durable provider-session audit contains only redacted metadata. A fake
database password is placed in the runtime `DATABASE_URL` environment variable;
the backup and reconstruction services remove that variable from child-process
environments and use the configured engine connection instead.

The drill scans every column of every source table, the manifest, the raw
custom-format dump, a data-only SQL expansion of that dump, and every column
of every restored table after recovery bootstrap and context capture. This
includes research records, evidence, claims, reports, audit, historical and
new RecoveryContexts, authorization records, provider-session audit, and
command metadata. It asserts that none of the fake sentinels appears in any
reviewed persistent field or backup artifact.

A separate command-construction test places a fake password in an engine URL
without connecting. It confirms that `pg_dump` and `pg_restore` receive it
only through `PGPASSWORD`, never command arguments, while `DATABASE_URL` is
removed. The drill does not change or expose the PostgreSQL server password.
