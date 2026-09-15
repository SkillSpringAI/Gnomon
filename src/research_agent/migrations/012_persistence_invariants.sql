-- Database-level invariants for governed memory records.
-- Applied migrations are immutable; this migration is additive.

ALTER TABLE memory_changes
    ADD CONSTRAINT memory_changes_previous_version_ck CHECK (previous_version >= 0);
ALTER TABLE memory_changes
    ADD CONSTRAINT memory_changes_version_positive_ck CHECK (version >= 1);
ALTER TABLE memory_changes
    ADD CONSTRAINT memory_changes_operation_ck
        CHECK (operation IN ('CREATE', 'UPDATE', 'ARCHIVE', 'LOGICAL_DELETE', 'RESTORE', 'REVERSE'));

