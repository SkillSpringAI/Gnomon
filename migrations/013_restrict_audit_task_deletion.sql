-- Retained audit events must survive ordinary task lifecycle operations.
-- Physical deletion of a task with audit history is intentionally rejected.

ALTER TABLE research_events
    DROP CONSTRAINT IF EXISTS research_events_task_id_fkey;
ALTER TABLE research_events
    ADD CONSTRAINT research_events_task_id_fkey
    FOREIGN KEY (task_id) REFERENCES research_tasks(id) ON DELETE RESTRICT;
