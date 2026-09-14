ALTER TABLE research_cycle_attempts
    ADD COLUMN IF NOT EXISTS evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE research_cycle_attempts
    ADD COLUMN IF NOT EXISTS claim_ids JSONB NOT NULL DEFAULT '[]'::jsonb;
