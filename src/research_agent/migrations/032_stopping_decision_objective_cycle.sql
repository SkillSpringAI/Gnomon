-- Persist the cycle identity for stopping-decision objective references.
-- Nullable preserves legacy decisions that did not identify a cycle.
ALTER TABLE stopping_decisions
    ADD COLUMN IF NOT EXISTS objective_cycle_number INTEGER;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stopping_decisions_objective_cycle_number_ck'
    ) THEN
        ALTER TABLE stopping_decisions
            ADD CONSTRAINT stopping_decisions_objective_cycle_number_ck
            CHECK (objective_cycle_number IS NULL OR objective_cycle_number >= 1);
    END IF;
END
$$;
