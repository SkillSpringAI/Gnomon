CREATE TABLE IF NOT EXISTS operator_authorizations (
    authorization_id UUID PRIMARY KEY CHECK (authorization_id <> '00000000-0000-0000-0000-000000000000'),
    authority_epoch_id UUID NOT NULL CHECK (authority_epoch_id <> '00000000-0000-0000-0000-000000000000'),
    security_state_version INTEGER NOT NULL CHECK (security_state_version >= 1),
    issued_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL CHECK (expires_at > issued_at),
    replay_id UUID NOT NULL CHECK (replay_id <> '00000000-0000-0000-0000-000000000000'),
    recovery_context_id UUID CHECK (recovery_context_id IS NULL OR recovery_context_id <> '00000000-0000-0000-0000-000000000000'),
    authorization_document JSONB NOT NULL CHECK (jsonb_typeof(authorization_document) = 'object'),
    command JSONB NOT NULL CHECK (jsonb_typeof(command) = 'object')
);
CREATE INDEX IF NOT EXISTS operator_authorizations_epoch_idx
    ON operator_authorizations (authority_epoch_id, issued_at, authorization_id);

CREATE TABLE IF NOT EXISTS execution_authorizations (
    execution_authorization_id UUID PRIMARY KEY CHECK (execution_authorization_id <> '00000000-0000-0000-0000-000000000000'),
    execution_id UUID NOT NULL CHECK (execution_id <> '00000000-0000-0000-0000-000000000000'),
    operator_authorization_id UUID NOT NULL REFERENCES operator_authorizations(authorization_id) ON DELETE RESTRICT,
    authority_epoch_id UUID NOT NULL CHECK (authority_epoch_id <> '00000000-0000-0000-0000-000000000000'),
    security_state_version INTEGER NOT NULL CHECK (security_state_version >= 1),
    issued_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL CHECK (expires_at > issued_at),
    replay_id UUID NOT NULL CHECK (replay_id <> '00000000-0000-0000-0000-000000000000'),
    recovery_context_id UUID CHECK (recovery_context_id IS NULL OR recovery_context_id <> '00000000-0000-0000-0000-000000000000'),
    authorization_document JSONB NOT NULL CHECK (jsonb_typeof(authorization_document) = 'object'),
    command JSONB NOT NULL CHECK (jsonb_typeof(command) = 'object')
);
CREATE INDEX IF NOT EXISTS execution_authorizations_operator_idx
    ON execution_authorizations (operator_authorization_id, issued_at, execution_authorization_id);

CREATE TABLE IF NOT EXISTS authorization_audit (
    artifact_id UUID PRIMARY KEY CHECK (artifact_id <> '00000000-0000-0000-0000-000000000000'),
    artifact_type TEXT NOT NULL CHECK (artifact_type IN ('operator_authorization', 'execution_authorization')),
    event_type TEXT NOT NULL CHECK (event_type IN ('authorization.operator_issued', 'authorization.execution_issued')),
    actor_type TEXT NOT NULL CHECK (actor_type = 'local_operator'),
    actor_id TEXT NOT NULL CHECK (actor_id = 'local-authorization-service'),
    authority_epoch_id UUID NOT NULL CHECK (authority_epoch_id <> '00000000-0000-0000-0000-000000000000'),
    security_state_version INTEGER NOT NULL CHECK (security_state_version >= 1),
    created_at TIMESTAMPTZ NOT NULL
);
