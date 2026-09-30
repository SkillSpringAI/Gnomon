# Provider Configuration

Provider credentials are configuration secrets, not research data. They must never be written to tasks, sources, claims, reports, logs, analytics, or audit-event payloads, and API responses must not return credentials or full secret-bearing configuration.

## Current backend behavior

The backend supports `LLM_API_KEY` as an environment-backed secret and an optional AWS Bedrock adapter. Bedrock is enabled only when `LLM_PROVIDER=bedrock`; configure `MODEL_ID`, `AWS_REGION`, and `LLM_TIMEOUT_SECONDS` through environment-backed settings. The standard boto3 credential chain and AWS-supported `AWS_BEARER_TOKEN_BEDROCK` variable may be used for temporary local runs. Credentials must never be committed or copied into application state.

Provider usage is bounded by configurable output-token, report-size, and per-task draft limits. Exceeding a limit returns a rate or payload error, records only a fixed failure reason, and does not send the report to the provider.

## Session credentials

Local development can use `POST /provider/session` to place a bearer token in a short-lived in-memory session scoped by an HttpOnly cookie and restricted to loopback requests. The endpoint is enabled automatically in local, development, and test environments. A non-local deployment must explicitly set `PROVIDER_SESSION_ENABLED=true`; loopback and Origin checks remain enforced and deployment cookies are Secure.

This is a local bridge for testing, not an authentication system for a deployed multi-user UI. Production use requires an authenticated identity and encrypted session management.

With PostgreSQL persistence, a session becomes usable only after its redacted
CREATE audit transaction is confirmed committed. A DELETE request removes the
process-local session before database access and audit authorization; if either
fails, or if the audit commit outcome is uncertain, the old cookie may remain
in the client but cannot retrieve the token. Replacement likewise
drops the old session once its commit is attempted, and publishes the new one
only after confirmed commit. A definite failure while staging a replacement
before commit leaves the old session available. These choices can lose a local
session rather than retain a credential whose governance outcome is uncertain.
There is no automatic retry.

Audit records describe accepted local session actions. They contain no token
or session identifier, do not recreate a session after restart, and do not
prove that an external provider credential was revoked. A CREATE audit can
survive a lost commit acknowledgement while no new in-memory session is
published. A request that already obtained a token before local deletion
cannot be retroactively cancelled.

The lost-acknowledgement tests inject an exception after a real database
commit. They validate service behavior under that uncertain outcome; they do
not reproduce a PostgreSQL network-level lost acknowledgement.

## Opt-in local Bedrock test configuration

Create a local-only configuration file from the tracked, placeholder-only
example:

```powershell
Copy-Item .env.bedrock-live.example .env.bedrock-live.local
```

Run the copy command only once. Running it again overwrites the edited local
file with the example placeholder; the pytest command does not copy or edit
the file.

Edit `.env.bedrock-live.local` and replace `<SET_LOCALLY>` with only the plain
Bedrock API-key value after `AWS_BEARER_TOKEN_BEDROCK=`. Do not paste an AWS
Windows shell command, `$Env:` assignment, quotes from that command, or a
`Bearer ` prefix into the value. The local file is ignored by Git; the example
is safe to commit. Never commit the bearer token. The dedicated test loads only
this file, overrides the required provider settings for its own scope, then
restores the prior
process environment and settings cache. Normal tests do not read the file or
require Bedrock credentials, and the live test is not part of ordinary CI.
Normal collection does not require the optional AWS package; the offline
client-construction and live-generation checks require `.[dev,aws]`.
The opted-in harness also uses temporary empty AWS config and credentials
files and suppresses inherited AWS profile and IAM credential sources. This
keeps the Bedrock API-key test independent of local AWS CLI configuration;
it does not edit or delete that configuration. Bedrock bearer authentication
does not itself require `botocore[crt]`.

Run the configuration-only check explicitly from the repository root:

```powershell
$Env:RUN_LIVE_BEDROCK_TESTS = "1"
python -m pytest tests/integration/test_bedrock_live.py::test_bedrock_live_configuration_reaches_provider_status_without_a_request -v
Remove-Item Env:RUN_LIVE_BEDROCK_TESTS -ErrorAction SilentlyContinue
```

That targeted check reaches only the application's provider-status
configuration boundary and sends no provider request. The separate
`test_bedrock_live_production_client_constructs_without_a_request` check
constructs the production Bedrock Runtime client offline. The
`test_one_live_bedrock_generation_through_gnomon` test attempts one real
generation when explicitly selected with `RUN_LIVE_BEDROCK_TESTS=1`.
Running the entire file with that flag also selects the live-generation test.
The generation test uses a temporary observer around the existing production
client call. Its output contains only selected status, AWS metadata, usage,
and local parsing results; it does not include prompts, draft text, response
bodies, headers, or credentials. The observer makes no additional request.
Do not paste token values into commands, logs, or test output.

The current optional `boto3>=1.35` floor does not guarantee Bedrock
bearer-token support. A separately justified minimum SDK version remains a
follow-up; no dependency minimum is changed by the live-test harness.

## Design requirements for future UI work

- Show the active provider and model without displaying the key.
- Return only success or a redacted error category from connection tests.
- Support removing or rotating a credential.
- Distinguish user-supplied credentials from application-managed credentials.
- Keep provider selection separate from research content and task state.

The domain and research database should know only the provider name and model identifier used for an operation; they should not know the credential value.
