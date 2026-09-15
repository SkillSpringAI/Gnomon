ALTER TABLE research_cycles
ADD COLUMN IF NOT EXISTS progress_tracked BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE research_cycles
ADD COLUMN IF NOT EXISTS recovery_reason TEXT;
