-- Preserve the five supported cycle status values at the persistence boundary.
-- Existing invalid rows must stop the upgrade for operator investigation.
ALTER TABLE research_cycles
    ADD CONSTRAINT research_cycles_status_valid
    CHECK (status IN ('planned', 'active', 'completed', 'blocked', 'failed'));
