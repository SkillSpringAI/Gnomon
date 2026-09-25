"""M2.6 canonical reconstruction fixture coverage."""

from uuid import uuid4

import pytest
from m2_reconstruction_fixture import (
    CANONICAL_RECONSTRUCTION_TABLES,
    canonical_fixture_table_counts,
    seed_canonical_reconstruction_fixture,
)
from sqlalchemy import create_engine, text

from research_agent.application.migrations import run_migrations
from research_agent.persistence.database import engine


@pytest.fixture
def reconstruction_fixture_db():
    schema = "m2_reconstruction_fixture_test_" + uuid4().hex
    with engine.begin() as conn:
        conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    isolated = create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        run_migrations(isolated)
        yield isolated
    finally:
        isolated.dispose()
        with engine.begin() as conn:
            conn.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')


def test_canonical_fixture_populates_every_m2_family(reconstruction_fixture_db):
    with reconstruction_fixture_db.begin() as conn:
        fixture = seed_canonical_reconstruction_fixture(conn)
        counts = canonical_fixture_table_counts(conn)
        security = conn.execute(
            text("SELECT state, version, authority_epoch_id FROM security_state WHERE id = 1")
        ).one()

    assert fixture.variant == "baseline"
    assert fixture.security_state == "normal"
    assert fixture.security_state_version == 3
    assert security.state == "normal"
    assert security.version == 3
    assert security.authority_epoch_id == fixture.authority_epoch_id
    assert fixture.provider_attempt_status == "SUCCEEDED"
    assert fixture.cycle_attempt_status == "COMPLETED"
    assert set(counts) == set(CANONICAL_RECONSTRUCTION_TABLES)
    assert all(count > 0 for count in counts.values())
    assert counts["research_cycles"] == 2
    assert counts["research_sources"] == 2
    assert counts["research_claims"] == 2
    assert counts["security_state_transitions"] == 2
    assert counts["authorization_audit"] == 2


def test_restrictive_unresolved_variant_marks_recovery_relevant_state(
    reconstruction_fixture_db,
):
    with reconstruction_fixture_db.begin() as conn:
        fixture = seed_canonical_reconstruction_fixture(
            conn,
            variant="restrictive_unresolved",
        )
        provider_status = conn.scalar(text("SELECT status FROM report_generation_attempts"))
        cycle_attempt_status = conn.scalar(text("SELECT status FROM research_cycle_attempts"))
        recovery_context = conn.scalar(text("SELECT context FROM recovery_contexts"))
        security = conn.execute(
            text("SELECT state, version FROM security_state WHERE id = 1")
        ).one()
        transition_count = conn.scalar(text("SELECT count(*) FROM security_state_transitions"))

    assert fixture.security_state == "lockdown"
    assert fixture.security_state_version == 4
    assert security.state == "lockdown"
    assert security.version == 4
    assert provider_status == "UNKNOWN"
    assert cycle_attempt_status == "INTERRUPTED"
    assert recovery_context["unresolved_operations"][0]["kind"] == "provider_attempt"
    assert transition_count == 3
