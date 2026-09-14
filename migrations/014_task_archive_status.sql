-- Add the governed archive terminal state without editing migration 001.

ALTER TABLE research_tasks DROP CONSTRAINT IF EXISTS research_tasks_status_check;
ALTER TABLE research_tasks
    ADD CONSTRAINT research_tasks_status_check
    CHECK (status IN ('planned', 'active', 'paused', 'blocked', 'concluded', 'abandoned', 'archived'));
