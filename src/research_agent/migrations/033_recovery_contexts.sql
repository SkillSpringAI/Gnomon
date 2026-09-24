CREATE TABLE IF NOT EXISTS recovery_contexts (
    context_id UUID PRIMARY KEY CHECK (context_id <> '00000000-0000-0000-0000-000000000000'),
    incident_id UUID NOT NULL CHECK (incident_id <> '00000000-0000-0000-0000-000000000000'),
    authority_epoch_id UUID NOT NULL CHECK (authority_epoch_id <> '00000000-0000-0000-0000-000000000000'),
    security_state_version INTEGER NOT NULL CHECK (security_state_version >= 1),
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL CHECK (expires_at > created_at),
    context JSONB NOT NULL CHECK (jsonb_typeof(context) = 'object'),
    command JSONB NOT NULL CHECK (jsonb_typeof(command) = 'object')
);
CREATE INDEX IF NOT EXISTS recovery_contexts_incident_idx
    ON recovery_contexts (incident_id, created_at, context_id);

CREATE TABLE IF NOT EXISTS recovery_context_audit (
    context_id UUID PRIMARY KEY REFERENCES recovery_contexts(context_id) ON DELETE RESTRICT,
    event_type TEXT NOT NULL CHECK (event_type = 'recovery.context_recorded'),
    actor_type TEXT NOT NULL CHECK (actor_type = 'local_operator'),
    actor_id TEXT NOT NULL CHECK (actor_id = 'local-recovery-diagnostics'),
    authority_epoch_id UUID NOT NULL,
    security_state_version INTEGER NOT NULL CHECK (security_state_version >= 1),
    created_at TIMESTAMPTZ NOT NULL
);
