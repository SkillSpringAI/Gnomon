CREATE TABLE IF NOT EXISTS security_state_transitions (
    transition_id UUID PRIMARY KEY,
    previous_state TEXT NOT NULL CHECK (
        previous_state IN ('normal', 'degraded', 'compromised_suspected', 'lockdown', 'recovery_required')
    ),
    new_state TEXT NOT NULL CHECK (
        new_state IN ('normal', 'degraded', 'compromised_suspected', 'lockdown', 'recovery_required')
    ),
    reason_code TEXT NOT NULL CHECK (reason_code IN (
        'OPERATOR_LOCKDOWN', 'SECURITY_INVARIANT_VIOLATION', 'INTEGRITY_CHECK_FAILED',
        'CREDENTIAL_COMPROMISE_SUSPECTED', 'AUTHORITY_BOUNDARY_VIOLATION',
        'SECURITY_DEPENDENCY_DEGRADED', 'RECOVERY_STARTED', 'RECOVERY_VERIFIED',
        'RECOVERY_PARTIAL', 'RECOVERY_FAILED', 'OPERATOR_DEGRADED_MODE'
    )),
    actor_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    security_state_version INTEGER NOT NULL CHECK (security_state_version >= 2),
    related_event_ids JSONB NOT NULL DEFAULT '[]'::jsonb
);
