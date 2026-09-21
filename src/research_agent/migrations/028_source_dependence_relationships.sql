-- Task-scoped, operator-attributed source-dependence relationships.
-- Current state and immutable change history are deliberately separate.
ALTER TABLE research_sources
    ADD CONSTRAINT research_sources_task_id_id_uk UNIQUE (task_id, id);

CREATE TABLE IF NOT EXISTS source_relationships (
    relationship_id UUID PRIMARY KEY,
    task_id UUID NOT NULL REFERENCES research_tasks(id) ON DELETE RESTRICT,
    source_low_id UUID NOT NULL,
    source_high_id UUID NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('derived_from', 'common_origin')),
    direction TEXT NOT NULL CHECK (direction IN ('low_to_high', 'high_to_low', 'none')),
    lifecycle TEXT NOT NULL CHECK (lifecycle IN ('active', 'retracted')),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    latest_change_id UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CHECK (source_low_id < source_high_id),
    CHECK (
        (kind = 'common_origin' AND direction = 'none')
        OR (kind = 'derived_from' AND direction IN ('low_to_high', 'high_to_low'))
    ),
    UNIQUE (task_id, source_low_id, source_high_id, kind),
    UNIQUE (relationship_id, task_id),
    CONSTRAINT source_relationships_low_source_fk
        FOREIGN KEY (task_id, source_low_id)
        REFERENCES research_sources (task_id, id)
        ON DELETE RESTRICT,
    CONSTRAINT source_relationships_high_source_fk
        FOREIGN KEY (task_id, source_high_id)
        REFERENCES research_sources (task_id, id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS source_relationship_changes (
    change_id UUID PRIMARY KEY,
    operation_id UUID NOT NULL UNIQUE,
    relationship_id UUID NOT NULL,
    task_id UUID NOT NULL,
    previous_revision INTEGER NOT NULL CHECK (previous_revision >= 0),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    operation TEXT NOT NULL CHECK (operation IN ('CREATE', 'SET', 'RETRACT', 'REVERSE')),
    previous_state JSONB,
    resulting_state JSONB NOT NULL,
    actor_type TEXT NOT NULL CHECK (actor_type = 'local_operator'),
    actor_id TEXT NOT NULL CHECK (length(actor_id) BETWEEN 1 AND 255),
    reason TEXT NOT NULL CHECK (length(reason) BETWEEN 1 AND 255),
    authority_epoch_id UUID NOT NULL,
    security_state_version INTEGER NOT NULL CHECK (security_state_version >= 1),
    reverses_change_id UUID,
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (relationship_id, revision),
    UNIQUE (relationship_id, reverses_change_id),
    CONSTRAINT source_relationship_changes_relationship_fk
        FOREIGN KEY (relationship_id, task_id)
        REFERENCES source_relationships (relationship_id, task_id)
        ON DELETE RESTRICT,
    CONSTRAINT source_relationship_changes_reverse_fk
        FOREIGN KEY (reverses_change_id)
        REFERENCES source_relationship_changes (change_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS source_relationships_task_endpoint_idx
    ON source_relationships (task_id, source_low_id, source_high_id);
CREATE INDEX IF NOT EXISTS source_relationship_changes_task_idx
    ON source_relationship_changes (task_id, relationship_id, revision);
