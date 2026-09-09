-- Durable lifecycle and provenance for bounded research cycle outcomes.
ALTER TABLE research_cycles ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;
ALTER TABLE research_cycles ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;
ALTER TABLE research_cycles ADD COLUMN IF NOT EXISTS result_summary TEXT;
ALTER TABLE research_cycles ADD COLUMN IF NOT EXISTS evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE research_cycles ADD COLUMN IF NOT EXISTS claim_ids JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE research_cycles ADD COLUMN IF NOT EXISTS unresolved_objectives JSONB NOT NULL DEFAULT '[]'::jsonb;
