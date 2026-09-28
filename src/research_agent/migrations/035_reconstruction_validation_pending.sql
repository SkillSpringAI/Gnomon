ALTER TABLE security_state
    ADD COLUMN IF NOT EXISTS reconstruction_validation_pending BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE security_state
    DROP CONSTRAINT IF EXISTS security_state_reconstruction_validation_pending_shape;

ALTER TABLE security_state
    ADD CONSTRAINT security_state_reconstruction_validation_pending_shape CHECK (
        reconstruction_validation_pending = FALSE
        OR (
            recovery_bootstrap_pending = TRUE
            AND recovery_bootstrap_started_at IS NOT NULL
            AND recovery_bootstrap_from_state IS NOT NULL
            AND recovery_bootstrap_from_version IS NOT NULL
            AND version > recovery_bootstrap_from_version
        )
    );
