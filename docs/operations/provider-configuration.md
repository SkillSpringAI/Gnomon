# Provider Configuration

Provider credentials are configuration secrets, not research data. They must never be written to tasks, sources, claims, reports, logs, analytics, or audit-event payloads, and API responses must not return credentials or full secret-bearing configuration.

## Current backend behavior

The backend supports `LLM_API_KEY` as an environment-backed secret and an optional AWS Bedrock adapter. Bedrock is enabled only when `LLM_PROVIDER=bedrock`; configure `MODEL_ID`, `AWS_REGION`, and `LLM_TIMEOUT_SECONDS` through environment-backed settings. The standard boto3 credential chain and AWS-supported `AWS_BEARER_TOKEN_BEDROCK` variable may be used for temporary local runs. Credentials must never be committed or copied into application state.

Provider usage is bounded by configurable output-token, report-size, and per-task draft limits. Exceeding a limit returns a rate or payload error, records only a fixed failure reason, and does not send the report to the provider.

## Session credentials

Local development can use `POST /provider/session` to place a bearer token in a short-lived in-memory session scoped by an HttpOnly cookie and restricted to loopback requests. The endpoint is enabled automatically in local, development, and test environments. A non-local deployment must explicitly set `PROVIDER_SESSION_ENABLED=true`; loopback and Origin checks remain enforced and deployment cookies are Secure.

This is a local bridge for testing, not an authentication system for a deployed multi-user UI. Production use requires an authenticated identity and encrypted session management.

## Design requirements for future UI work

- Show the active provider and model without displaying the key.
- Return only success or a redacted error category from connection tests.
- Support removing or rotating a credential.
- Distinguish user-supplied credentials from application-managed credentials.
- Keep provider selection separate from research content and task state.

The domain and research database should know only the provider name and model identifier used for an operation; they should not know the credential value.
