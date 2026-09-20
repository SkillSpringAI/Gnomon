"""Direct SQL cannot bypass critical durable invariants."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from research_agent.application.migrations import run_migrations
from research_agent.persistence.database import engine

run_migrations(engine)


def test_authority_invariant_constraints_have_stable_names() -> None:
    expected = {
        "security_state_singleton_id_valid",
        "security_state_state_valid",
        "security_state_version_positive",
        "security_state_epoch_non_nil",
        "security_state_recovery_bootstrap_shape",
        "security_state_transitions_previous_state_valid",
        "security_state_transitions_new_state_valid",
        "security_state_transitions_version_valid",
    }
    replaced = {
        "security_state_id_check",
        "security_state_state_check",
        "security_state_version_check",
        "security_state_transitions_previous_state_check",
        "security_state_transitions_new_state_check",
        "security_state_transitions_security_state_version_check",
    }
    with engine.connect() as connection:
        names = set(
            connection.scalars(
                text(
                    """
                    SELECT conname
                    FROM pg_constraint
                    WHERE conrelid IN (
                        'security_state'::regclass,
                        'security_state_transitions'::regclass
                    )
                    """
                )
            )
        )
    assert expected <= names
    assert names.isdisjoint(replaced)


def _insert_security_transition(
    *,
    previous_state: str = "normal",
    new_state: str = "lockdown",
    security_state_version: int = 2,
) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO security_state_transitions (
                    transition_id, previous_state, new_state, reason_code,
                    actor_type, actor_id, created_at, security_state_version,
                    related_event_ids
                ) VALUES (
                    :transition_id, :previous_state, :new_state, 'OPERATOR_LOCKDOWN',
                    'local_operator', 'persistence-invariant-test', now(),
                    :security_state_version, '[]'::jsonb
                )
                """
            ),
            {
                "transition_id": uuid4(),
                "previous_state": previous_state,
                "new_state": new_state,
                "security_state_version": security_state_version,
            },
        )


def test_direct_sql_rejects_noncanonical_security_singleton_identity() -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO security_state (
                        id, state, version, authority_epoch_id, updated_at
                    ) VALUES (2, 'normal', 1, :authority_epoch_id, now())
                    """
                ),
                {"authority_epoch_id": uuid4()},
            )


def test_direct_sql_rejects_invalid_canonical_security_state() -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(text("UPDATE security_state SET state = 'invalid' WHERE id = 1"))


@pytest.mark.parametrize("version", [0, -1])
def test_direct_sql_rejects_nonpositive_canonical_security_version(version: int) -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE security_state SET version = :version WHERE id = 1"),
                {"version": version},
            )


@pytest.mark.parametrize("authority_epoch_id", [None, UUID(int=0)])
def test_direct_sql_rejects_missing_or_nil_canonical_epoch(
    authority_epoch_id: UUID | None,
) -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE security_state SET authority_epoch_id = :authority_epoch_id "
                    "WHERE id = 1"
                ),
                {"authority_epoch_id": authority_epoch_id},
            )


@pytest.mark.parametrize(
    "set_clause",
    [
        "recovery_bootstrap_pending = true",
        "recovery_bootstrap_started_at = now()",
        (
            "recovery_bootstrap_pending = true, recovery_bootstrap_started_at = now(), "
            "recovery_bootstrap_from_state = 'invalid', recovery_bootstrap_from_version = 1"
        ),
        (
            "recovery_bootstrap_pending = true, recovery_bootstrap_started_at = now(), "
            "recovery_bootstrap_from_state = 'normal', recovery_bootstrap_from_version = 0"
        ),
    ],
    ids=[
        "pending-without-origin",
        "origin-without-pending",
        "invalid-origin-state",
        "nonpositive-origin-version",
    ],
)
def test_direct_sql_rejects_invalid_recovery_bootstrap_tuple(set_clause: str) -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(text(f"UPDATE security_state SET {set_clause} WHERE id = 1"))


@pytest.mark.parametrize("column", ["previous_state", "new_state"])
def test_direct_sql_rejects_invalid_security_transition_state(column: str) -> None:
    values = {"previous_state": "normal", "new_state": "lockdown"}
    values[column] = "invalid"
    with pytest.raises(IntegrityError):
        _insert_security_transition(**values)


@pytest.mark.parametrize("version", [1, 0, -1])
def test_direct_sql_rejects_security_transition_version_below_two(version: int) -> None:
    with pytest.raises(IntegrityError):
        _insert_security_transition(security_state_version=version)


def test_direct_sql_rejects_invalid_memory_version() -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO memory_changes (
                        change_id, task_id, target_type, target_id, operation, actor,
                        timestamp, previous_version, version, proposed_state,
                        resulting_state, reason, provenance, request
                    ) VALUES (
                        :change_id, :task_id, 'claim', :target_id, 'CREATE', 'test',
                        now(), -1, 0, '{}'::jsonb, '{} '::jsonb, 'invalid',
                        '[]'::jsonb, '{}'::jsonb
                    )
                    """
                ),
                {"change_id": uuid4(), "task_id": uuid4(), "target_id": uuid4()},
            )


def test_direct_sql_rejects_unknown_memory_operation() -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO memory_changes (
                        change_id, task_id, target_type, target_id, operation, actor,
                        timestamp, previous_version, version, proposed_state,
                        resulting_state, reason, provenance, request
                    ) VALUES (
                        :change_id, :task_id, 'claim', :target_id, 'INVALID', 'test',
                        now(), 0, 1, '{}'::jsonb, '{}'::jsonb, 'invalid',
                        '[]'::jsonb, '{}'::jsonb
                    )
                    """
                ),
                {"change_id": uuid4(), "task_id": uuid4(), "target_id": uuid4()},
            )


def test_direct_sql_rejects_task_delete_with_retained_audit_event() -> None:
    task_id = uuid4()
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO research_tasks
                        (id, title, objective, status, brief, plan, created_at, updated_at)
                    VALUES (:task_id, 'retention test', 'retention test', 'archived',
                            '{}'::jsonb, '{}'::jsonb, now(), now())
                    """
                ),
                {"task_id": task_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO research_events (id, task_id, event_type, payload, created_at)
                    VALUES (:event_id, :task_id, 'retention.test', '{}'::jsonb, now())
                    """
                ),
                {"event_id": uuid4(), "task_id": task_id},
            )
            connection.execute(
                text("DELETE FROM research_tasks WHERE id = :task_id"),
                {"task_id": task_id},
            )
