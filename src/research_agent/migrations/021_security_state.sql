CREATE TABLE IF NOT EXISTS security_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    state TEXT NOT NULL CHECK (
        state IN ('normal', 'degraded', 'compromised_suspected', 'lockdown', 'recovery_required')
    ),
    version INTEGER NOT NULL CHECK (version >= 1),
    updated_at TIMESTAMPTZ NOT NULL
);

INSERT INTO security_state (id, state, version, updated_at)
VALUES (1, 'normal', 1, now())
ON CONFLICT (id) DO NOTHING;
