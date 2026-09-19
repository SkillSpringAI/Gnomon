-- Only the first introduction of the column initializes a continuing installation.
-- No persistent default: missing/corrupt lineage must never mint a replacement.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'security_state'
          AND column_name = 'authority_epoch_id'
    ) THEN
        IF NOT EXISTS (SELECT 1 FROM security_state WHERE id = 1) THEN
            RAISE EXCEPTION 'Cannot initialize authority epoch: security state is missing';
        END IF;
        ALTER TABLE security_state ADD COLUMN authority_epoch_id UUID;
        UPDATE security_state SET authority_epoch_id = gen_random_uuid() WHERE id = 1;
        ALTER TABLE security_state ALTER COLUMN authority_epoch_id SET NOT NULL;
        ALTER TABLE security_state ADD CONSTRAINT security_state_epoch_non_nil
            CHECK (authority_epoch_id <> '00000000-0000-0000-0000-000000000000'::uuid);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM security_state WHERE id = 1 AND authority_epoch_id IS NOT NULL
          AND authority_epoch_id <> '00000000-0000-0000-0000-000000000000'::uuid
    ) THEN
        RAISE EXCEPTION 'Canonical authority epoch is missing or invalid';
    END IF;
END $$;

-- Existing audit is historical and remains unbound; all new service writes bind epoch.
ALTER TABLE security_state_transitions ADD COLUMN IF NOT EXISTS authority_epoch_id UUID
    CHECK (authority_epoch_id <> '00000000-0000-0000-0000-000000000000'::uuid);
