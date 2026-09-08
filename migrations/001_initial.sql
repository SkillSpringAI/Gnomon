-- Initial persistence schema for open-ended research investigations.
-- Apply through the project's migration runner once PostgreSQL is available.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS research_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    objective TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('planned', 'active', 'paused', 'blocked', 'concluded', 'abandoned')),
    brief JSONB NOT NULL,
    plan JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS research_cycles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES research_tasks(id) ON DELETE CASCADE,
    cycle_number INTEGER NOT NULL CHECK (cycle_number > 0),
    objectives JSONB NOT NULL,
    methods JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned',
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (task_id, cycle_number)
);

CREATE TABLE IF NOT EXISTS research_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES research_tasks(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS research_tasks_status_idx ON research_tasks (status);
CREATE INDEX IF NOT EXISTS research_cycles_task_idx ON research_cycles (task_id, cycle_number);
CREATE INDEX IF NOT EXISTS research_events_task_idx ON research_events (task_id, created_at);
