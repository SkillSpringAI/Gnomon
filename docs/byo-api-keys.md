# Bring Your Own API Key Design

## Goal

When a user interface is added, users should be able to use their own model-provider credentials without the project becoming dependent on one shared key or requiring the open-source maintainer to pay for every request.

## Rules

- API keys are configuration secrets, not research data.
- Keys must never be written to research tasks, sources, claims, reports, logs, analytics, or audit-event payloads.
- API responses must never return a key or a full provider configuration containing a key.
- Keys must not be included in prompts, source records, error messages, or model-visible content.
- The application should use a redacted `SecretStr`-style representation in memory and logs.
- Provider calls must have explicit timeouts, usage limits, and failure handling.

## User-facing modes

### Local or self-hosted mode

The user supplies a key through an environment variable, local secret store, or deployment secret. This is the safest initial mode for an open-source release.

### UI session mode

The user may enter a key in the UI for the current session. The backend should keep it only in short-lived process/session memory or an encrypted secret store with an explicit expiration policy. The raw key should not be persisted in PostgreSQL.

### Managed mode

An operator may provide a server-side provider configuration for users who do not bring their own key. This should be an explicit deployment choice, not an assumption in the core application.

## Provider abstraction

The research agent should depend on a provider interface that accepts a structured request and returns validated structured output. The provider implementation owns authentication, model selection, timeout handling, retries, token/cost accounting, and provider-specific error mapping.

The domain and research database should know only the provider name and model identifier used for an operation. They should not know the credential value.

## UI requirements for later

- Show which provider and model are active without displaying the key.
- Offer a “test connection” action that returns only success or a redacted error category.
- Allow the user to remove or rotate the key.
- Clearly distinguish user-supplied credentials from application-managed credentials.
- Keep provider selection separate from research content and task state.

## Initial implementation decision

The current backend supports `LLM_API_KEY` as an environment-backed secret and keeps it out of response models. A future UI can add a session-scoped credential provider without changing the research-task, evidence, or provenance schema.
