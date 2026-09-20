ALTER TABLE security_state
    ADD COLUMN IF NOT EXISTS recovery_bootstrap_pending BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS recovery_bootstrap_started_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS recovery_bootstrap_from_state TEXT,
    ADD COLUMN IF NOT EXISTS recovery_bootstrap_from_version INTEGER;

ALTER TABLE security_state
    DROP CONSTRAINT IF EXISTS security_state_recovery_bootstrap_shape;

ALTER TABLE security_state
    ADD CONSTRAINT security_state_recovery_bootstrap_shape CHECK (
        (
            recovery_bootstrap_pending = FALSE
            AND recovery_bootstrap_started_at IS NULL
            AND recovery_bootstrap_from_state IS NULL
            AND recovery_bootstrap_from_version IS NULL
        )
        OR
        (
            recovery_bootstrap_pending = TRUE
            AND recovery_bootstrap_started_at IS NOT NULL
            AND recovery_bootstrap_from_state IN (
                'normal', 'degraded', 'compromised_suspected', 'lockdown', 'recovery_required'
            )
            AND recovery_bootstrap_from_version >= 1
        )
    );
