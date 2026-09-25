"""M2.7 deterministic reconstruction equivalence helpers."""

from uuid import uuid4

import pytest
from m2_reconstruction_equivalence import (
    ReconstructionEquivalenceMismatch,
    assert_reconstruction_equivalent,
    projection_for,
)
from m2_reconstruction_fixture import seed_canonical_reconstruction_fixture
from sqlalchemy import create_engine, text

from research_agent.application.migrations import run_migrations
from research_agent.persistence.database import engine


@pytest.fixture
def equivalence_dbs():
    source_schema = "m2_equivalence_source_" + uuid4().hex
    restored_schema = "m2_equivalence_restored_" + uuid4().hex
    with engine.begin() as conn:
        conn.exec_driver_sql(f'CREATE SCHEMA "{source_schema}"')
        conn.exec_driver_sql(f'CREATE SCHEMA "{restored_schema}"')
    source = create_engine(
        engine.url,
        connect_args={"options": f"-csearch_path={source_schema}"},
    )
    restored = create_engine(
        engine.url,
        connect_args={"options": f"-csearch_path={restored_schema}"},
    )
    try:
        run_migrations(source)
        run_migrations(restored)
        yield source, restored
    finally:
        source.dispose()
        restored.dispose()
        with engine.begin() as conn:
            conn.exec_driver_sql(f'DROP SCHEMA "{source_schema}" CASCADE')
            conn.exec_driver_sql(f'DROP SCHEMA "{restored_schema}" CASCADE')


def test_equivalence_accepts_matching_canonical_fixture(equivalence_dbs):
    source, restored = equivalence_dbs
    with source.begin() as source_conn:
        source_fixture = seed_canonical_reconstruction_fixture(source_conn)
    with restored.begin() as restored_conn:
        restored_conn.execute(
            text(
                """
                UPDATE security_state
                SET authority_epoch_id = :authority_epoch_id
                WHERE id = 1
                """
            ),
            {"authority_epoch_id": source_fixture.authority_epoch_id},
        )
        restored_fixture = seed_canonical_reconstruction_fixture(restored_conn)

    assert source_fixture.task_id == restored_fixture.task_id
    assert_reconstruction_equivalent(
        source,
        restored,
        task_id=source_fixture.task_id,
    )
    projection = projection_for(source, task_id=source_fixture.task_id)
    assert set(projection.groups) == {
        "research",
        "evidence_provenance",
        "assessments",
        "source_dependence",
        "memory",
        "stopping",
        "execution_attempts",
        "provider_attempts",
        "audit",
        "security_epoch",
        "recovery_authorization",
        "migration_state",
    }
    assert projection.snapshot["task"]["id"] == str(source_fixture.task_id)
    assert projection.report["task_id"] == str(source_fixture.task_id)


def test_equivalence_reports_first_changed_group(equivalence_dbs):
    source, restored = equivalence_dbs
    with source.begin() as source_conn:
        source_fixture = seed_canonical_reconstruction_fixture(
            source_conn,
            variant="restrictive_unresolved",
        )
    with restored.begin() as restored_conn:
        restored_conn.execute(
            text(
                """
                UPDATE security_state
                SET authority_epoch_id = :authority_epoch_id
                WHERE id = 1
                """
            ),
            {"authority_epoch_id": source_fixture.authority_epoch_id},
        )
        seed_canonical_reconstruction_fixture(
            restored_conn,
            variant="restrictive_unresolved",
        )
        restored_conn.execute(
            text(
                """
                UPDATE report_generation_attempts
                SET status = 'FAILED', error_reason = 'fixture mutation'
                """
            )
        )

    with pytest.raises(
        ReconstructionEquivalenceMismatch,
        match="provider_attempts",
    ):
        assert_reconstruction_equivalent(
            source,
            restored,
            task_id=source_fixture.task_id,
        )
