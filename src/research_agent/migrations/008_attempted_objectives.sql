ALTER TABLE research_cycles
ADD COLUMN IF NOT EXISTS attempted_objectives JSONB NOT NULL DEFAULT '[]'::jsonb;
