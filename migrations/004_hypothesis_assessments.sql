-- Evidence-backed assessments of investigation hypotheses.

CREATE TABLE IF NOT EXISTS hypothesis_assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES research_tasks(id) ON DELETE CASCADE,
    hypothesis_id UUID NOT NULL,
    status TEXT NOT NULL,
    summary TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    updated_at TIMESTAMPTZ NOT NULL,
    UNIQUE (task_id, hypothesis_id)
);

CREATE TABLE IF NOT EXISTS assessment_evidence (
    assessment_id UUID NOT NULL REFERENCES hypothesis_assessments(id) ON DELETE CASCADE,
    claim_id UUID NOT NULL REFERENCES research_claims(id) ON DELETE CASCADE,
    relation TEXT NOT NULL,
    strength DOUBLE PRECISION NOT NULL CHECK (strength >= 0 AND strength <= 1),
    PRIMARY KEY (assessment_id, claim_id)
);

CREATE INDEX IF NOT EXISTS hypothesis_assessments_task_idx ON hypothesis_assessments (task_id);
