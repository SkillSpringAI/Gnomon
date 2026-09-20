"""Fresh, continuing, and recovery startup authority boundaries."""

from uuid import uuid4

import pytest
from conftest import purge_test_tasks
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from research_agent.adapters.agents.fake import FakeAgentNetwork
from research_agent.api.app import create_app
from research_agent.api.routes.evidence import get_source_retriever
from research_agent.application.authority_bootstrap import (
    AuthorityBootstrapService,
    AuthorityBootstrapUnavailable,
    AuthorityStartupMode,
)
from research_agent.application.evidence_service import EvidenceService
from research_agent.application.migrations import migration_files
from research_agent.application.provider_budget_service import ProviderBudgetService
from research_agent.application.report_generation_service import ReportGenerationService
from research_agent.application.research_service import ResearchService
from research_agent.application.security_capability import SecurityCapabilityDenied
from research_agent.application.security_state_store import SecurityStateStore
from research_agent.application.source_registry import SourceRegistryService
from research_agent.config.settings import get_settings
from research_agent.domain.research import (
    ClaimCreate,
    ClaimSourceLink,
    ResearchBrief,
    SourceCreate,
    SourceType,
    TrustedSourceCreate,
)
from research_agent.persistence.database import SessionFactory, engine
from research_agent.persistence.models import (
    ReportGenerationAttemptRecord,
    ResearchCycleAttemptRecord,
    ResearchSourceRecord,
    SecurityStateRecord,
    TrustedSourceRecord,
)
from research_agent.persistence.repositories import SqlAlchemyResearchTaskRepository


@pytest.fixture
def isolated_bootstrap_connection():
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            schema = "bootstrap_test_" + uuid4().hex
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}", public')
            for path in migration_files():
                connection.exec_driver_sql(path.read_text(encoding="utf-8"))
            yield connection
        finally:
            transaction.rollback()


def test_fresh_bootstrap_accepts_only_a_pristine_new_install(isolated_bootstrap_connection):
    connection = isolated_bootstrap_connection
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        initial = AuthorityBootstrapService(session).initialize(AuthorityStartupMode.FRESH)
        assert initial.state.value == "normal"
        assert initial.version == 1
        session.add(
            TrustedSourceRecord(
                id=uuid4(),
                domain="restored.example",
                display_name="Restored",
                source_type="web_page",
                verification_method="historical",
                requires_attribution=True,
                status="enabled",
            )
        )
        session.commit()
        with pytest.raises(AuthorityBootstrapUnavailable, match="pristine"):
            AuthorityBootstrapService(session).initialize(AuthorityStartupMode.FRESH)


def test_continuing_startup_preserves_epoch_state_and_version(isolated_bootstrap_connection):
    connection = isolated_bootstrap_connection
    connection.execute(text("UPDATE security_state SET state='lockdown', version=7"))
    before = connection.execute(text("SELECT to_jsonb(s) FROM security_state s")).scalar_one()
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        loaded = AuthorityBootstrapService(session).initialize(AuthorityStartupMode.CONTINUING)
        assert loaded.state.value == "lockdown"
        assert loaded.version == 7
    after = connection.execute(text("SELECT to_jsonb(s) FROM security_state s")).scalar_one()
    assert after == before


def test_recovery_bootstrap_fences_restored_authority_before_reconciliation(
    monkeypatch,
):
    with engine.begin() as connection:
        original_security = dict(
            connection.execute(text("SELECT * FROM security_state WHERE id=1")).mappings().one()
        )
        connection.execute(
            text(
                "UPDATE security_state SET state='normal', version=7, "
                "recovery_bootstrap_pending=false, recovery_bootstrap_started_at=null, "
                "recovery_bootstrap_from_state=null, recovery_bootstrap_from_version=null"
            )
        )
    task_id = None
    trusted_id = None
    try:
        with SessionFactory() as session:
            research = ResearchService(SqlAlchemyResearchTaskRepository(session))
            task = research.create_task(
                ResearchBrief(title="Restored task", objective="Must remain inert")
            )
            task_id = task.id
            attempt_id = uuid4()
            research.start_cycle(
                task.id, 1, exclusive=True, track_progress=True, attempt_id=attempt_id
            )
            source = EvidenceService(session).create_source(
                task.id,
                SourceCreate(
                    source_type=SourceType.DOCUMENT,
                    title="Historical evidence",
                    content="Historical evidence must remain inert during recovery bootstrap.",
                ),
            )
            EvidenceService(session).create_claim(
                task.id,
                ClaimCreate(
                    statement="Historical claim",
                    confidence=0.4,
                    source_links=[
                        ClaimSourceLink(source_id=source.id, support_type="supporting")
                    ],
                ),
            )
            registry = SourceRegistryService(session)
            trusted = registry.register(
                TrustedSourceCreate(
                    domain="restored-authority.example",
                    display_name="Restored authority",
                    verification_method="historical",
                )
            )
            trusted_id = trusted.id
            registry.enable(trusted.domain)
            provider_operation = uuid4()
            ProviderBudgetService(session).reserve(task.id, provider_operation, 20, 30)

        calls = {"source": 0, "agent": 0, "provider": 0}

        class Retriever:
            def fetch(self, target):
                calls["source"] += 1
                raise AssertionError("Recovery bootstrap dispatched source retrieval")

        def discover(*args, **kwargs):
            calls["agent"] += 1
            raise AssertionError("Recovery bootstrap dispatched an agent")

        def generate(*args, **kwargs):
            calls["provider"] += 1
            raise AssertionError("Recovery bootstrap dispatched a provider")

        monkeypatch.setattr(FakeAgentNetwork, "discover", discover)
        monkeypatch.setattr(ReportGenerationService, "generate", generate)
        monkeypatch.setenv("AUTHORITY_STARTUP_MODE", "recovery")
        get_settings.cache_clear()
        app = create_app()
        app.dependency_overrides[get_source_retriever] = lambda: Retriever()
        with TestClient(app) as client:
            current = client.get("/security/state")
            assert current.status_code == 200
            assert current.json()["state"] == "recovery_required"
            assert current.json()["version"] == 8
            assert (
                client.post(
                    f"/investigations/{task.id}/cycles/1/run-sources",
                    json={
                        "sources": [
                            {
                                "uri": "https://restored-authority.example/evidence",
                                "objective_index": 0,
                            }
                        ]
                    },
                ).status_code
                == 403
            )
            agent_run = client.post(f"/investigations/{task.id}/cycles/1/run", json={})
            assert agent_run.status_code == 403
            assert client.post(f"/investigations/{task.id}/cycles/1/start").status_code == 403
            assert client.post(f"/investigations/{task.id}/report/draft").status_code == 403
            assert (
                client.post(
                    "/security/transitions",
                    json={
                        "expected_version": 8,
                        "requested_state": "lockdown",
                        "reason_code": "OPERATOR_LOCKDOWN",
                    },
                ).status_code
                == 403
            )

        assert calls == {"source": 0, "agent": 0, "provider": 0}
        with SessionFactory() as session:
            state = SecurityStateStore(session).load()
            raw = session.get(SecurityStateRecord, 1)
            assert state.state.value == "recovery_required"
            assert state.recovery_bootstrap_pending
            assert raw is not None and raw.state == "normal" and raw.version == 8
            assert raw.authority_epoch_id == original_security["authority_epoch_id"]
            assert raw.recovery_bootstrap_from_state == "normal"
            assert raw.recovery_bootstrap_from_version == 7
            with pytest.raises(SecurityCapabilityDenied):
                EvidenceService(session).create_source(
                    task.id,
                    SourceCreate(
                        source_type=SourceType.DOCUMENT,
                        title="Forbidden",
                        content="This ordinary memory mutation must not commit.",
                    ),
                )
            with pytest.raises(SecurityCapabilityDenied):
                ProviderBudgetService(session).dispatch(provider_operation)
        with SessionFactory() as session:
            provider_attempt = session.get(ReportGenerationAttemptRecord, provider_operation)
            assert provider_attempt is not None and provider_attempt.status == "PENDING"
            attempt = session.get(ResearchCycleAttemptRecord, attempt_id)
            assert attempt is not None and attempt.status == "RUNNING"
            assert session.get(TrustedSourceRecord, trusted_id).status == "enabled"
            assert (
                len(
                    session.scalars(
                        select(ResearchSourceRecord).where(
                            ResearchSourceRecord.task_id == task.id
                        )
                    ).all()
                )
                == 1
            )

        monkeypatch.setenv("AUTHORITY_STARTUP_MODE", "continuing")
        get_settings.cache_clear()
        with TestClient(create_app()) as client:
            restarted = client.get("/security/state").json()
            assert restarted["state"] == "recovery_required"
            assert restarted["version"] == 8
            assert restarted["authority_epoch_id"] == str(
                original_security["authority_epoch_id"]
            )
    finally:
        get_settings.cache_clear()
        with engine.begin() as connection:
            if task_id is not None:
                purge_test_tasks(connection, [task_id])
            if trusted_id is not None:
                connection.execute(
                    delete(TrustedSourceRecord).where(TrustedSourceRecord.id == trusted_id)
                )
            connection.execute(
                text("""
                UPDATE security_state SET
                    state=:state, version=:version, updated_at=:updated_at,
                    authority_epoch_id=:authority_epoch_id,
                    recovery_bootstrap_pending=:recovery_bootstrap_pending,
                    recovery_bootstrap_started_at=:recovery_bootstrap_started_at,
                    recovery_bootstrap_from_state=:recovery_bootstrap_from_state,
                    recovery_bootstrap_from_version=:recovery_bootstrap_from_version
                WHERE id=1
                """),
                original_security,
            )
