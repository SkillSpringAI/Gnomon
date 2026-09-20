-- Give the constitutional authority checks stable names without changing their
-- predicates. Fallback creation covers an unexpectedly missing legacy check;
-- validation then fails the migration if existing data violates the invariant.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'security_state'::regclass
          AND conname = 'security_state_singleton_id_valid'
    ) THEN
        IF EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'security_state'::regclass
              AND conname = 'security_state_id_check'
        ) THEN
            EXECUTE 'ALTER TABLE security_state RENAME CONSTRAINT '
                'security_state_id_check TO security_state_singleton_id_valid';
        ELSE
            EXECUTE 'ALTER TABLE security_state ADD CONSTRAINT '
                'security_state_singleton_id_valid CHECK (id = 1) NOT VALID';
        END IF;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'security_state'::regclass
          AND conname = 'security_state_state_valid'
    ) THEN
        IF EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'security_state'::regclass
              AND conname = 'security_state_state_check'
        ) THEN
            EXECUTE 'ALTER TABLE security_state RENAME CONSTRAINT '
                'security_state_state_check TO security_state_state_valid';
        ELSE
            EXECUTE 'ALTER TABLE security_state ADD CONSTRAINT '
                'security_state_state_valid CHECK (state IN '
                '(''normal'', ''degraded'', ''compromised_suspected'', '
                '''lockdown'', ''recovery_required'')) NOT VALID';
        END IF;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'security_state'::regclass
          AND conname = 'security_state_version_positive'
    ) THEN
        IF EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'security_state'::regclass
              AND conname = 'security_state_version_check'
        ) THEN
            EXECUTE 'ALTER TABLE security_state RENAME CONSTRAINT '
                'security_state_version_check TO security_state_version_positive';
        ELSE
            EXECUTE 'ALTER TABLE security_state ADD CONSTRAINT '
                'security_state_version_positive CHECK (version >= 1) NOT VALID';
        END IF;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'security_state_transitions'::regclass
          AND conname = 'security_state_transitions_previous_state_valid'
    ) THEN
        IF EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'security_state_transitions'::regclass
              AND conname = 'security_state_transitions_previous_state_check'
        ) THEN
            EXECUTE 'ALTER TABLE security_state_transitions RENAME CONSTRAINT '
                'security_state_transitions_previous_state_check TO '
                'security_state_transitions_previous_state_valid';
        ELSE
            EXECUTE 'ALTER TABLE security_state_transitions ADD CONSTRAINT '
                'security_state_transitions_previous_state_valid CHECK (previous_state IN '
                '(''normal'', ''degraded'', ''compromised_suspected'', '
                '''lockdown'', ''recovery_required'')) NOT VALID';
        END IF;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'security_state_transitions'::regclass
          AND conname = 'security_state_transitions_new_state_valid'
    ) THEN
        IF EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'security_state_transitions'::regclass
              AND conname = 'security_state_transitions_new_state_check'
        ) THEN
            EXECUTE 'ALTER TABLE security_state_transitions RENAME CONSTRAINT '
                'security_state_transitions_new_state_check TO '
                'security_state_transitions_new_state_valid';
        ELSE
            EXECUTE 'ALTER TABLE security_state_transitions ADD CONSTRAINT '
                'security_state_transitions_new_state_valid CHECK (new_state IN '
                '(''normal'', ''degraded'', ''compromised_suspected'', '
                '''lockdown'', ''recovery_required'')) NOT VALID';
        END IF;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'security_state_transitions'::regclass
          AND conname = 'security_state_transitions_version_valid'
    ) THEN
        IF EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'security_state_transitions'::regclass
              AND conname = 'security_state_transitions_security_state_version_check'
        ) THEN
            EXECUTE 'ALTER TABLE security_state_transitions RENAME CONSTRAINT '
                'security_state_transitions_security_state_version_check TO '
                'security_state_transitions_version_valid';
        ELSE
            EXECUTE 'ALTER TABLE security_state_transitions ADD CONSTRAINT '
                'security_state_transitions_version_valid '
                'CHECK (security_state_version >= 2) NOT VALID';
        END IF;
    END IF;
END $$;

ALTER TABLE security_state
    VALIDATE CONSTRAINT security_state_singleton_id_valid;
ALTER TABLE security_state
    VALIDATE CONSTRAINT security_state_state_valid;
ALTER TABLE security_state
    VALIDATE CONSTRAINT security_state_version_positive;
ALTER TABLE security_state_transitions
    VALIDATE CONSTRAINT security_state_transitions_previous_state_valid;
ALTER TABLE security_state_transitions
    VALIDATE CONSTRAINT security_state_transitions_new_state_valid;
ALTER TABLE security_state_transitions
    VALIDATE CONSTRAINT security_state_transitions_version_valid;

-- If a partially applied manual run left both forms, retain only the canonical name.
ALTER TABLE security_state DROP CONSTRAINT IF EXISTS security_state_id_check;
ALTER TABLE security_state DROP CONSTRAINT IF EXISTS security_state_state_check;
ALTER TABLE security_state DROP CONSTRAINT IF EXISTS security_state_version_check;
ALTER TABLE security_state_transitions
    DROP CONSTRAINT IF EXISTS security_state_transitions_previous_state_check;
ALTER TABLE security_state_transitions
    DROP CONSTRAINT IF EXISTS security_state_transitions_new_state_check;
ALTER TABLE security_state_transitions
    DROP CONSTRAINT IF EXISTS security_state_transitions_security_state_version_check;
