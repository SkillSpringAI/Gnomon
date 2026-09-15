ALTER TABLE research_cycles
ADD COLUMN IF NOT EXISTS objective_results JSONB NOT NULL DEFAULT '[]'::jsonb;
