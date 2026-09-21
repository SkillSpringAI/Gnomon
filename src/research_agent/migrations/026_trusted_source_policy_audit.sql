-- Durable, configuration-scoped audit events for trusted-source policy writes.
-- This is separate from task-scoped research_events and contains no source prose,
-- URLs, verification text, secrets, or raw request data.
CREATE TABLE IF NOT EXISTS trusted_source_policy_events (
    event_id UUID PRIMARY KEY,
    source_id UUID NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('REGISTER', 'ENABLE')),
    previous_status TEXT CHECK (previous_status IN ('enabled', 'disabled', 'review')),
    new_status TEXT NOT NULL CHECK (new_status IN ('enabled', 'disabled', 'review')),
    actor_type TEXT NOT NULL CHECK (actor_type = 'local_operator'),
    actor_id TEXT NOT NULL CHECK (length(actor_id) BETWEEN 1 AND 255),
    authority_epoch_id UUID NOT NULL,
    security_state_version INTEGER NOT NULL CHECK (security_state_version >= 1),
    result TEXT NOT NULL CHECK (result IN ('accepted', 'no_op')),
    reason TEXT NOT NULL CHECK (reason IN ('registered', 'enabled', 'already_enabled')),
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS trusted_source_policy_events_created_idx
    ON trusted_source_policy_events (created_at, event_id);
