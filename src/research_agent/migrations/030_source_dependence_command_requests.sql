-- Preserve the normalized command identity needed for safe idempotent replay.
-- Nullable keeps migration 028 history readable without inventing old requests.
ALTER TABLE source_relationship_changes
    ADD COLUMN IF NOT EXISTS command_request JSONB;
