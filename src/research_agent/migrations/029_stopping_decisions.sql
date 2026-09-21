-- Operator-controlled, task-scoped stopping decisions and immutable history.
ALTER TABLE research_tasks
    ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 1;

ALTER TABLE research_tasks
    ADD CONSTRAINT research_tasks_revision_ck CHECK (revision >= 1);

CREATE TABLE IF NOT EXISTS stopping_decisions (
    decision_id UUID PRIMARY KEY,
    task_id UUID NOT NULL UNIQUE REFERENCES research_tasks(id) ON DELETE RESTRICT,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    operation_id UUID NOT NULL UNIQUE,
    reason TEXT NOT NULL CHECK (reason IN (
        'evidence_sufficient', 'resource_limited',
        'evidence_unavailable', 'operator_stopped'
    )),
    rationale TEXT NOT NULL CHECK (length(rationale) BETWEEN 1 AND 4000),
    source_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    claim_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    objective_indices JSONB NOT NULL DEFAULT '[]'::jsonb,
    review_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    limitations JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_fingerprint TEXT NOT NULL CHECK (evidence_fingerprint ~ '^[0-9a-f]{64}$'),
    runtime_limit_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    actor_type TEXT NOT NULL CHECK (actor_type = 'local_operator'),
    actor_id TEXT NOT NULL CHECK (length(actor_id) BETWEEN 1 AND 255),
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (decision_id, task_id)
);

CREATE TABLE IF NOT EXISTS stopping_decision_changes (
    change_id UUID PRIMARY KEY,
    decision_id UUID NOT NULL,
    task_id UUID NOT NULL,
    operation_id UUID NOT NULL UNIQUE,
    previous_revision INTEGER NOT NULL CHECK (previous_revision >= 0),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    resulting_state JSONB NOT NULL,
    actor_type TEXT NOT NULL CHECK (actor_type = 'local_operator'),
    actor_id TEXT NOT NULL CHECK (length(actor_id) BETWEEN 1 AND 255),
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (decision_id, revision),
    FOREIGN KEY (decision_id, task_id)
        REFERENCES stopping_decisions (decision_id, task_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS stopping_decision_changes_task_idx
    ON stopping_decision_changes (task_id, decision_id, revision);
