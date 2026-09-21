-- Durable, redacted lifecycle audit for ephemeral provider credential sessions.
-- Tokens, cookie/session identifiers, and provider diagnostics are never stored.
CREATE TABLE IF NOT EXISTS provider_session_events (
    event_id UUID PRIMARY KEY,
    operation TEXT NOT NULL CHECK (operation IN ('CREATE', 'DELETE')),
    provider TEXT NOT NULL CHECK (provider IN ('stub', 'bedrock')),
    credential_mode TEXT NOT NULL CHECK (credential_mode = 'session_bearer_token'),
    ttl_seconds INTEGER CHECK (ttl_seconds IS NULL OR ttl_seconds BETWEEN 60 AND 43200),
    actor_type TEXT NOT NULL CHECK (actor_type = 'local_operator'),
    actor_id TEXT NOT NULL CHECK (length(actor_id) BETWEEN 1 AND 255),
    authority_epoch_id UUID NOT NULL,
    security_state_version INTEGER NOT NULL CHECK (security_state_version >= 1),
    result TEXT NOT NULL CHECK (result IN ('accepted', 'no_op')),
    reason TEXT NOT NULL CHECK (reason IN ('created', 'deleted', 'already_absent')),
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS provider_session_events_created_idx
    ON provider_session_events (created_at, event_id);
