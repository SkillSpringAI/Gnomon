-- Registry of domains approved for controlled source retrieval.

CREATE TABLE IF NOT EXISTS trusted_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    verification_method TEXT NOT NULL,
    requires_attribution BOOLEAN NOT NULL DEFAULT TRUE,
    status TEXT NOT NULL DEFAULT 'review',
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS trusted_sources_domain_idx ON trusted_sources (domain);
CREATE INDEX IF NOT EXISTS trusted_sources_status_idx ON trusted_sources (status);
