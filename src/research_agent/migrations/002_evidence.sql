-- Evidence and provenance schema for investigation claims.

CREATE TABLE IF NOT EXISTS research_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES research_tasks(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    title TEXT NOT NULL,
    uri TEXT,
    publisher TEXT,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    reliability_score DOUBLE PRECISION NOT NULL CHECK (reliability_score >= 0 AND reliability_score <= 1),
    observed_at TIMESTAMPTZ NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS research_claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES research_tasks(id) ON DELETE CASCADE,
    statement TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS claim_sources (
    claim_id UUID NOT NULL REFERENCES research_claims(id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES research_sources(id) ON DELETE CASCADE,
    support_type TEXT NOT NULL,
    strength DOUBLE PRECISION NOT NULL CHECK (strength >= 0 AND strength <= 1),
    PRIMARY KEY (claim_id, source_id)
);

CREATE INDEX IF NOT EXISTS research_sources_task_idx ON research_sources (task_id, observed_at);
CREATE INDEX IF NOT EXISTS research_claims_task_idx ON research_claims (task_id, created_at);
