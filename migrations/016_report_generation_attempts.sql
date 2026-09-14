-- Atomic provider-budget reservations and idempotent report generation attempts.

CREATE TABLE IF NOT EXISTS report_generation_attempts (
    operation_id UUID PRIMARY KEY,
    task_id UUID NOT NULL REFERENCES research_tasks(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'SUCCEEDED', 'FAILED', 'EXPIRED')),
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    error_reason TEXT
);
CREATE INDEX IF NOT EXISTS report_generation_attempts_task_idx
    ON report_generation_attempts(task_id, status, started_at);
