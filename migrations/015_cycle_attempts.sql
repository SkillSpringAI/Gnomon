-- Durable identity and stage for externally meaningful cycle executions.

CREATE TABLE IF NOT EXISTS research_cycle_attempts (
    id UUID PRIMARY KEY,
    task_id UUID NOT NULL REFERENCES research_tasks(id) ON DELETE CASCADE,
    cycle_id UUID NOT NULL REFERENCES research_cycles(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('RUNNING', 'COMPLETED', 'BLOCKED', 'FAILED', 'INTERRUPTED')),
    stage TEXT NOT NULL CHECK (stage IN (
        'CREATED', 'STARTED', 'QUESTIONING', 'EVIDENCE_RECORDED',
        'EXTRACTING_CLAIMS', 'FINALIZING', 'COMPLETED', 'BLOCKED', 'FAILED', 'INTERRUPTED'
    )),
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    recovery_reason TEXT
);
CREATE INDEX IF NOT EXISTS research_cycle_attempts_cycle_idx
    ON research_cycle_attempts(cycle_id, started_at, id);
