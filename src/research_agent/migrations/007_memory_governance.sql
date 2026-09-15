-- Additive governance of claims and assessments. Existing records start at v1;
-- their first governed mutation captures the available pre-migration state.
ALTER TABLE research_claims ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1
    CHECK (version > 0);
ALTER TABLE research_claims ADD COLUMN IF NOT EXISTS lifecycle TEXT NOT NULL DEFAULT 'active'
    CHECK (lifecycle IN ('active', 'archived', 'logically_deleted'));
ALTER TABLE hypothesis_assessments ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1
    CHECK (version > 0);
ALTER TABLE hypothesis_assessments ADD COLUMN IF NOT EXISTS lifecycle TEXT NOT NULL DEFAULT 'active'
    CHECK (lifecycle IN ('active', 'archived', 'logically_deleted'));

-- Deliberately no cascading task/target foreign key: deletion of current records
-- must not erase historical transitions. This journal is not a public audit feed.
CREATE TABLE IF NOT EXISTS memory_changes (
    change_id UUID PRIMARY KEY,
    task_id UUID NOT NULL,
    target_type TEXT NOT NULL CHECK (target_type IN ('claim', 'assessment')),
    target_id UUID NOT NULL,
    operation TEXT NOT NULL,
    actor TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    previous_version INTEGER NOT NULL,
    version INTEGER NOT NULL CHECK (version = previous_version + 1),
    previous_state JSONB,
    proposed_state JSONB NOT NULL,
    resulting_state JSONB NOT NULL,
    reason TEXT NOT NULL,
    provenance JSONB NOT NULL,
    request JSONB NOT NULL,
    reverses_change_id UUID UNIQUE REFERENCES memory_changes(change_id),
    UNIQUE (target_type, target_id, version)
);
CREATE INDEX IF NOT EXISTS memory_changes_task_idx
    ON memory_changes(task_id, timestamp, change_id);
