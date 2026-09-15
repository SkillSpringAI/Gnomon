ALTER TABLE report_generation_attempts
    DROP CONSTRAINT IF EXISTS report_generation_attempts_status_check;

ALTER TABLE report_generation_attempts
    ADD CONSTRAINT report_generation_attempts_status_check
    CHECK (status IN ('PENDING', 'DISPATCHED', 'SUCCEEDED', 'FAILED', 'EXPIRED'));
