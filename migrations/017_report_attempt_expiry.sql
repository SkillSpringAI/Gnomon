-- Pending provider reservations must be recoverable after a process timeout.

ALTER TABLE report_generation_attempts
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
UPDATE report_generation_attempts
SET expires_at = started_at + INTERVAL '5 minutes'
WHERE expires_at IS NULL;
ALTER TABLE report_generation_attempts
    ALTER COLUMN expires_at SET NOT NULL;
CREATE INDEX IF NOT EXISTS report_generation_attempts_expiry_idx
    ON report_generation_attempts(task_id, status, expires_at);
