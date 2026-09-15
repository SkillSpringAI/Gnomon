ALTER TABLE research_cycles
ADD COLUMN IF NOT EXISTS objective_reviews JSONB NOT NULL DEFAULT '[]'::jsonb;
