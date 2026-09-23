-- Preserve accepted commands separately from server-derived decision limitations.
-- Legacy history stays readable; absent original commands cannot prove replay identity.
ALTER TABLE stopping_decision_changes
    ADD COLUMN IF NOT EXISTS command_request JSONB;
