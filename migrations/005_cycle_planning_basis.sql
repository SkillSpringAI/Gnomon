-- Add stored per-objective planning reasons without rewriting existing cycles.
ALTER TABLE research_cycles
    ADD COLUMN IF NOT EXISTS planning_basis JSONB NOT NULL DEFAULT '[]'::jsonb;
