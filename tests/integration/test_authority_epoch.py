"""Authority lineage upgrades and corruption handling in isolated PostgreSQL schemas."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from research_agent.application.migrations import migration_files
from research_agent.application.security_state_service import (
    SecurityStateTransitionService,
    SecurityTransitionDenied,
)
from research_agent.application.security_state_store import (
    SecurityStateStore,
    SecurityStateUnavailable,
)
from research_agent.domain.security import SecurityActor, SecurityReasonCode, SecurityState
from research_agent.persistence.database import engine


@pytest.fixture
def legacy_connection():
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            schema = "epoch_test_" + uuid4().hex
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}", public')
            for path in migration_files():
                if path.name < "023":
                    connection.exec_driver_sql(path.read_text(encoding="utf-8"))
            yield connection
        finally:
            transaction.rollback()


def epoch_sql():
    return next(p for p in migration_files() if p.name.startswith("023_")).read_text(
        encoding="utf-8"
    )


def bootstrap_sql():
    return next(p for p in migration_files() if p.name.startswith("024_")).read_text(
        encoding="utf-8"
    )


def test_populated_upgrade_preserves_state_and_historical_audit(legacy_connection):
    connection = legacy_connection
    connection.execute(text("UPDATE security_state SET state='lockdown', version=2"))
    connection.execute(
        text("""
        INSERT INTO security_state_transitions
        (transition_id, previous_state, new_state, reason_code, actor_type, actor_id,
         created_at, security_state_version)
        VALUES (:id, 'normal', 'lockdown', 'OPERATOR_LOCKDOWN', 'local_operator',
                'legacy', now(), 2)
    """),
        {"id": uuid4()},
    )
    before = connection.scalar(text("SELECT to_jsonb(s) FROM security_state s"))
    audit = connection.scalar(text("SELECT to_jsonb(s) FROM security_state_transitions s"))
    connection.exec_driver_sql(epoch_sql())
    after = connection.scalar(text("SELECT to_jsonb(s) FROM security_state s"))
    epoch = UUID(after.pop("authority_epoch_id"))
    assert epoch.int != 0
    assert after == before
    after_audit = connection.scalar(text("SELECT to_jsonb(s) FROM security_state_transitions s"))
    assert after_audit.pop("authority_epoch_id") is None
    assert after_audit == audit
    connection.exec_driver_sql(epoch_sql())
    assert connection.scalar(text("SELECT authority_epoch_id FROM security_state")) == epoch


def test_legacy_missing_state_cannot_initialize_epoch(legacy_connection):
    legacy_connection.execute(text("DELETE FROM security_state"))
    with pytest.raises(DBAPIError, match="security state is missing"):
        legacy_connection.exec_driver_sql(epoch_sql())


@pytest.mark.parametrize("corruption", ["null", "nil", "missing"])
def test_corruption_never_regenerates_epoch(legacy_connection, corruption):
    connection = legacy_connection
    connection.exec_driver_sql(epoch_sql())
    connection.exec_driver_sql(bootstrap_sql())
    # Simulate corrupted storage by bypassing constraints in this rollback-only schema.
    if corruption == "missing":
        connection.execute(text("DELETE FROM security_state"))
    elif corruption == "null":
        connection.execute(
            text("ALTER TABLE security_state ALTER authority_epoch_id DROP NOT NULL")
        )
        connection.execute(text("UPDATE security_state SET authority_epoch_id=NULL"))
    else:
        connection.execute(
            text("ALTER TABLE security_state DROP CONSTRAINT security_state_epoch_non_nil")
        )
        connection.execute(
            text("UPDATE security_state SET authority_epoch_id=:epoch"), {"epoch": UUID(int=0)}
        )
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        with pytest.raises(SecurityStateUnavailable):
            SecurityStateStore(session).load()
        with pytest.raises(SecurityTransitionDenied):
            SecurityStateTransitionService(session).transition(
                expected_version=1,
                requested_state=SecurityState.NORMAL,
                actor_type=SecurityActor.LOCAL_OPERATOR,
                actor_id="test",
                reason_code=SecurityReasonCode.OPERATOR_DEGRADED_MODE,
            )
    with pytest.raises(DBAPIError, match="Canonical authority epoch is missing or invalid"):
        connection.exec_driver_sql(epoch_sql())


@pytest.mark.parametrize("value", [None, UUID(int=0), "malformed"])
def test_database_rejects_invalid_epoch(legacy_connection, value):
    connection = legacy_connection
    connection.exec_driver_sql(epoch_sql())
    with pytest.raises(DBAPIError):
        connection.execute(
            text("UPDATE security_state SET authority_epoch_id=:epoch"), {"epoch": value}
        )
