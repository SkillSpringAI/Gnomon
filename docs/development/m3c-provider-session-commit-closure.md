# M3c provider-session commit-boundary closure

**Status:** The bounded provider credential-session CREATE/DELETE slice is
formally closed. Implementation:
`0c55a279dc1664789203794b114e9439f75bf38e`. At verification,
`HEAD == origin/main` at that SHA and the working tree was clean. Hosted
[Quality run 36522924832](https://github.com/SkillSpringAI/Gnomon/actions/runs/36522924832)
was triggered by its push, reported that exact `headSha`, and passed `checks`,
`browser`, and `minimal-install`. This documentation-only closure follows the
tested implementation. It does not close all of M3c or begin provider-attempt
or external-effect reconciliation.

CREATE now stages and flushes its redacted audit before replacing any existing
local session. The new token enters the lookup store only after `commit()`
returns successfully. A definite pre-commit failure can preserve the old
session. Once commit is attempted, the old session is gone and an uncertain
outcome cannot publish the proposed new session or restore the old one. DELETE
removes the process-local token before database access and keeps it absent
after setup, authorization, staging, or commit failure. The store lock spans
each governed mutation, so a new lookup cannot acquire a session during its
commit window. Retained client cookies are inert when the local token is gone;
restart does not reconstruct secrets from durable audit. A request that already
obtained a token before deletion cannot be retroactively cancelled.

The audit records governed **local session actions**, not live secret
availability or revocation at the external provider. A committed CREATE audit
can outlive a lost acknowledgement without a published token; a failed DELETE
audit can coexist with a locally destroyed token. Neither audit row contains
the credential or session identifier. Changed application paths do not log
the token, failure-response tests assert the secret is absent, and inspection
of the hosted job logs found no provider-token sentinel exposure. The tests
inject an exception after a real database commit to verify service behavior
under an uncertain outcome; they **do not reproduce a PostgreSQL network-level
lost acknowledgement**. No automatic retry or new persistence-error category
was added.

The hosted normal suite reported **1,928 passed, 28 skipped**. All skips were
the opt-in browser cases; there were no PostgreSQL-client or provider-session
skips. The provider-session integration file ran in that suite, including the
synthetic post-commit, pre-commit, concurrent lookup, two-delete, inert-cookie,
and restart contracts. The separate Chromium job reported **28 passed, zero
skipped**. All three Quality jobs completed successfully with no unexpected
test or workflow failure.

The `checks` job applied all **36 migrations** to a fresh PostgreSQL database;
the prototype rerun applied none. Database-wheel verification confirmed all
36 packaged migration resources and their checksums, and passed schema,
populated upgrade, rerun, drift rejection, and draft checks. The separate
`minimal-install` job passed the base-wheel memory API and provider-status
checks without AWS dependencies. Before commit, focused local verification
reported 104 passed; the normal local suite reported 1,923 passed and 33
skipped (five missing `pg_dump`/`pg_restore` cases plus 28 opt-in browser
cases). Ruff, source-tree mypy, changed-file formatting, and `git diff
--check` passed. The hosted run supplies the PostgreSQL-client evidence that
the local environment lacked.

The [Pass 1 characterization](m3c-pass1-ambiguous-commit-characterization.md)
remains the historical record of the former unsafe ordering. The
[provider-session procedure](../operations/provider-configuration.md) states
the current fail-closed and audit semantics. Provider-attempt and external
provider-effect ambiguity remain separate M3c work; this closure makes no
claim about them or about administrator-level audit tamper resistance.
