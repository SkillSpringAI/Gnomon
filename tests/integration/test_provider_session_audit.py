"""Durable, redacted provider-session lifecycle audit contracts."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import contextmanager
from threading import Barrier, Event
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, text

from research_agent.api.app import create_app
from research_agent.api.routes import provider as provider_module
from research_agent.api.routes import reports as reports_module
from research_agent.application import provider_session_audit as audit_module
from research_agent.application.provider_session import ProviderSessionStore
from research_agent.application.security_capability import (
    SecurityCapability,
    SecurityCapabilityDenied,
)
from research_agent.persistence.database import engine
from research_agent.persistence.models import ProviderSessionEventRecord


@pytest.fixture(autouse=True)
def clean_provider_session_events():
    with engine.begin() as connection:
        connection.execute(delete(ProviderSessionEventRecord))
        connection.execute(
            text(
                "UPDATE security_state SET state = 'normal', version = 1, "
                "updated_at = now() WHERE id = 1"
            )
        )
    yield
    with engine.begin() as connection:
        connection.execute(delete(ProviderSessionEventRecord))
        connection.execute(
            text(
                "UPDATE security_state SET state = 'normal', version = 1, "
                "updated_at = now() WHERE id = 1"
            )
        )


def test_provider_session_create_delete_and_repeat_are_audited_without_secrets(
    monkeypatch,
):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    from research_agent.config.settings import get_settings

    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            created = client.post(
                "/provider/session",
                json={"bearer_token": "secret-" + uuid4().hex, "ttl_seconds": 600},
            )
            assert created.status_code == 201
            assert "secret-" not in created.text
            session_id = client.cookies.get("provider_session")
            assert session_id is not None
            assert provider_module.provider_sessions.get(session_id) is not None
            deleted = client.delete("/provider/session")
            assert deleted.status_code == 204
            assert provider_module.provider_sessions.get(session_id) is None
            repeated = client.delete("/provider/session")
            assert repeated.status_code == 204

            response = client.get("/provider/audit")
            assert response.status_code == 200
            payload = response.json()
            assert {event["reason"] for event in payload} == {
                "deleted",
                "already_absent",
                "created",
            }
            assert all(event["credential_mode"] == "session_bearer_token" for event in payload)
            assert "secret-" not in response.text
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        get_settings.cache_clear()


def test_replacing_active_provider_session_audits_revoke_then_create(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    from research_agent.config.settings import get_settings

    get_settings.cache_clear()
    first_secret = "first-secret-" + uuid4().hex
    second_secret = "second-secret-" + uuid4().hex
    try:
        with TestClient(create_app()) as client:
            first = client.post(
                "/provider/session",
                json={"bearer_token": first_secret, "ttl_seconds": 600},
            )
            assert first.status_code == 201
            replaced = client.post(
                "/provider/session",
                json={"bearer_token": second_secret, "ttl_seconds": 900},
            )
            assert replaced.status_code == 201

            events = client.get("/provider/audit").json()
            assert [event["operation"] for event in events].count("CREATE") == 2
            assert [event["operation"] for event in events].count("DELETE") == 1
            assert all(event["reason"] in {"created", "deleted"} for event in events)
            assert first_secret not in replaced.text
            assert second_secret not in replaced.text
            assert first_secret not in str(events)
            assert second_secret not in str(events)
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        get_settings.cache_clear()


def test_commit_call_failure_revokes_old_session_without_publishing_new_one(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    from research_agent.config.settings import get_settings

    get_settings.cache_clear()
    first_secret = "first-secret-" + uuid4().hex
    second_secret = "second-secret-" + uuid4().hex
    try:
        with TestClient(create_app(), raise_server_exceptions=False) as client:
            created = client.post(
                "/provider/session",
                json={"bearer_token": first_secret, "ttl_seconds": 600},
            )
            assert created.status_code == 201
            old_session_id = client.cookies.get("provider_session")
            assert old_session_id is not None

            real_factory = provider_module.SessionFactory

            @contextmanager
            def failing_factory():
                with real_factory() as session:

                    def fail_commit():
                        raise RuntimeError("injected audit commit failure")

                    session.commit = fail_commit
                    yield session

            monkeypatch.setattr(provider_module, "SessionFactory", failing_factory)
            failed = client.post(
                "/provider/session",
                json={"bearer_token": second_secret, "ttl_seconds": 900},
            )
            assert failed.status_code == 500
            assert client.cookies.get("provider_session") == old_session_id
            assert provider_module.provider_sessions.get(old_session_id) is None
            assert (
                client.get("/provider/status").json()["credential_mode"] != "session_bearer_token"
            )
            assert second_secret not in failed.text
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        get_settings.cache_clear()


def test_post_commit_exception_never_restores_replaced_session(monkeypatch):
    """Simulate an exception after DB commit, not a real lost PostgreSQL ACK."""
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    from research_agent.config.settings import get_settings

    get_settings.cache_clear()
    first_secret = "first-ack-secret-" + uuid4().hex
    second_secret = "second-ack-secret-" + uuid4().hex
    try:
        with TestClient(create_app(), raise_server_exceptions=False) as client:
            created = client.post(
                "/provider/session",
                json={"bearer_token": first_secret, "ttl_seconds": 600},
            )
            assert created.status_code == 201
            old_session_id = client.cookies.get("provider_session")
            assert old_session_id is not None

            real_factory = provider_module.SessionFactory

            @contextmanager
            def post_commit_failure_factory():
                with real_factory() as session:
                    real_commit = session.commit

                    def committed_then_lost_ack():
                        real_commit()
                        raise RuntimeError("simulated lost commit acknowledgement")

                    session.commit = committed_then_lost_ack
                    yield session

            monkeypatch.setattr(provider_module, "SessionFactory", post_commit_failure_factory)
            failed = client.post(
                "/provider/session",
                json={"bearer_token": second_secret, "ttl_seconds": 900},
            )
            assert failed.status_code == 500
            assert client.cookies.get("provider_session") == old_session_id
            assert provider_module.provider_sessions.get(old_session_id) is None
            with engine.connect() as connection:
                operations = connection.scalars(
                    text("SELECT operation FROM provider_session_events ORDER BY created_at")
                ).all()
            assert operations.count("CREATE") == 2
            assert operations.count("DELETE") == 1
            assert second_secret not in failed.text
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        get_settings.cache_clear()


def test_post_commit_exception_keeps_deleted_session_unusable(monkeypatch):
    """Synthetic lost ACK cannot revive the local token after committed audit."""
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    from research_agent.config.settings import get_settings

    get_settings.cache_clear()
    secret = "delete-ack-secret-" + uuid4().hex
    try:
        with TestClient(create_app(), raise_server_exceptions=False) as client:
            created = client.post(
                "/provider/session",
                json={"bearer_token": secret, "ttl_seconds": 600},
            )
            assert created.status_code == 201
            session_id = client.cookies.get("provider_session")
            assert session_id is not None

            real_factory = provider_module.SessionFactory

            @contextmanager
            def post_commit_failure_factory():
                with real_factory() as session:
                    real_commit = session.commit

                    def committed_then_lost_ack():
                        real_commit()
                        raise RuntimeError("simulated lost commit acknowledgement")

                    session.commit = committed_then_lost_ack
                    yield session

            monkeypatch.setattr(provider_module, "SessionFactory", post_commit_failure_factory)
            failed = client.delete("/provider/session")
            assert failed.status_code == 500
            assert client.cookies.get("provider_session") == session_id
            assert provider_module.provider_sessions.get(session_id) is None
            assert (
                client.get("/provider/status").json()["credential_mode"] != "session_bearer_token"
            )
            with engine.connect() as connection:
                operations = connection.scalars(
                    text("SELECT operation FROM provider_session_events")
                ).all()
            assert operations.count("CREATE") == 1
            assert operations.count("DELETE") == 1
            assert secret not in failed.text
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        get_settings.cache_clear()


def test_uncertain_initial_create_never_publishes_a_session(monkeypatch):
    """Real DB commit followed by synthetic ACK loss leaves no usable token."""
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    from research_agent.config.settings import get_settings

    get_settings.cache_clear()
    secret = "initial-ack-secret-" + uuid4().hex
    real_factory = provider_module.SessionFactory
    real_create = provider_module.provider_sessions.create
    published = Event()

    @contextmanager
    def post_commit_failure_factory():
        with real_factory() as session:
            real_commit = session.commit

            def committed_then_lost_ack():
                real_commit()
                raise RuntimeError("simulated lost commit acknowledgement")

            session.commit = committed_then_lost_ack
            yield session

    def observed_create(token, ttl_seconds):
        published.set()
        return real_create(token, ttl_seconds)

    monkeypatch.setattr(provider_module, "SessionFactory", post_commit_failure_factory)
    monkeypatch.setattr(provider_module.provider_sessions, "create", observed_create)
    try:
        with TestClient(create_app(), raise_server_exceptions=False) as client:
            failed = client.post(
                "/provider/session",
                json={"bearer_token": secret, "ttl_seconds": 600},
            )
            assert failed.status_code == 500
            assert client.cookies.get("provider_session") is None
            assert not published.is_set()
            with engine.connect() as connection:
                assert (
                    connection.scalar(
                        text(
                            "SELECT count(*) FROM provider_session_events "
                            "WHERE operation = 'CREATE'"
                        )
                    )
                    == 1
                )
            assert secret not in failed.text
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        get_settings.cache_clear()


def test_definite_precommit_initial_create_never_publishes_a_session(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    from research_agent.config.settings import get_settings

    get_settings.cache_clear()
    secret = "initial-stage-secret-" + uuid4().hex

    def fail_stage(*args, **kwargs):
        raise RuntimeError("injected pre-commit audit stage failure")

    monkeypatch.setattr(audit_module.ProviderSessionAuditService, "stage", fail_stage)
    try:
        with TestClient(create_app(), raise_server_exceptions=False) as client:
            failed = client.post(
                "/provider/session",
                json={"bearer_token": secret, "ttl_seconds": 600},
            )
            assert failed.status_code == 500
            assert client.cookies.get("provider_session") is None
            with engine.connect() as connection:
                assert connection.scalar(text("SELECT count(*) FROM provider_session_events")) == 0
            assert secret not in failed.text
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        get_settings.cache_clear()


def test_initial_create_publishes_only_after_confirmed_audit_commit(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    from research_agent.config.settings import get_settings

    get_settings.cache_clear()
    secret = "initial-publish-secret-" + uuid4().hex
    real_factory = provider_module.SessionFactory
    real_create = provider_module.provider_sessions.create
    entered_commit = Event()
    release_commit = Event()
    published = Event()

    @contextmanager
    def paused_factory():
        with real_factory() as session:
            real_commit = session.commit

            def paused_commit():
                entered_commit.set()
                assert release_commit.wait(timeout=10)
                real_commit()

            session.commit = paused_commit
            yield session

    def observed_create(token, ttl_seconds):
        published.set()
        return real_create(token, ttl_seconds)

    monkeypatch.setattr(provider_module, "SessionFactory", paused_factory)
    monkeypatch.setattr(provider_module.provider_sessions, "create", observed_create)
    try:

        def create_session():
            with TestClient(create_app()) as client:
                response = client.post(
                    "/provider/session",
                    json={"bearer_token": secret, "ttl_seconds": 600},
                )
                return response.status_code, client.cookies.get("provider_session")

        with ThreadPoolExecutor(max_workers=1) as executor:
            creation = executor.submit(create_session)
            try:
                assert entered_commit.wait(timeout=10)
                assert not published.is_set()
            finally:
                release_commit.set()
            status, session_id = creation.result(timeout=10)
        assert status == 201
        assert published.is_set()
        assert session_id is not None
        assert provider_module.provider_sessions.get(session_id) == secret
    finally:
        release_commit.set()
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        get_settings.cache_clear()


def test_definite_precommit_delete_failure_still_revokes_old_session(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    from research_agent.config.settings import get_settings

    get_settings.cache_clear()
    secret = "delete-stage-secret-" + uuid4().hex
    try:
        with TestClient(create_app(), raise_server_exceptions=False) as client:
            created = client.post(
                "/provider/session",
                json={"bearer_token": secret, "ttl_seconds": 600},
            )
            assert created.status_code == 201
            session_id = client.cookies.get("provider_session")
            assert session_id is not None

            def fail_stage(*args, **kwargs):
                raise RuntimeError("injected pre-commit audit stage failure")

            monkeypatch.setattr(audit_module.ProviderSessionAuditService, "stage", fail_stage)
            failed = client.delete("/provider/session")
            assert failed.status_code == 500
            assert client.cookies.get("provider_session") == session_id
            assert provider_module.provider_sessions.get(session_id) is None
            with engine.connect() as connection:
                assert (
                    connection.scalar(
                        text(
                            "SELECT count(*) FROM provider_session_events "
                            "WHERE operation = 'DELETE'"
                        )
                    )
                    == 0
                )
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        get_settings.cache_clear()


@pytest.mark.parametrize("failure_phase", ["session_factory", "authorization"])
def test_delete_revokes_even_if_database_setup_or_authorization_fails(monkeypatch, failure_phase):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    from research_agent.config.settings import get_settings

    get_settings.cache_clear()
    secret = "delete-early-failure-" + uuid4().hex
    try:
        with TestClient(create_app(), raise_server_exceptions=False) as client:
            created = client.post(
                "/provider/session",
                json={"bearer_token": secret, "ttl_seconds": 600},
            )
            assert created.status_code == 201
            session_id = client.cookies.get("provider_session")
            assert session_id is not None

            def fail_early(*args, **kwargs):
                raise RuntimeError("injected pre-transaction failure")

            if failure_phase == "session_factory":
                monkeypatch.setattr(provider_module, "SessionFactory", fail_early)
            else:
                monkeypatch.setattr(
                    audit_module.ProviderSessionAuditService, "authorize_delete", fail_early
                )
            failed = client.delete("/provider/session")
            assert failed.status_code == 500
            assert client.cookies.get("provider_session") == session_id
            assert provider_module.provider_sessions.get(session_id) is None
            with engine.connect() as connection:
                assert (
                    connection.scalar(
                        text(
                            "SELECT count(*) FROM provider_session_events "
                            "WHERE operation = 'DELETE'"
                        )
                    )
                    == 0
                )
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        get_settings.cache_clear()


@pytest.mark.parametrize("operation", ["replace", "delete"])
@pytest.mark.parametrize("lost_ack", [False, True])
def test_lookup_waits_for_session_commit_and_never_recovers_old_token(
    monkeypatch, operation, lost_ack
):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    from research_agent.config.settings import get_settings

    get_settings.cache_clear()
    old_secret = "concurrent-ack-old-" + uuid4().hex
    new_secret = "concurrent-ack-new-" + uuid4().hex
    entered_commit = Event()
    release_commit = Event()
    lookup_started = Event()
    try:
        with TestClient(create_app()) as setup:
            created = setup.post(
                "/provider/session",
                json={"bearer_token": old_secret, "ttl_seconds": 600},
            )
            assert created.status_code == 201
            old_session_id = setup.cookies.get("provider_session")
            assert old_session_id is not None

            real_factory = provider_module.SessionFactory

            @contextmanager
            def paused_factory():
                with real_factory() as session:
                    real_commit = session.commit

                    def paused_commit():
                        entered_commit.set()
                        assert release_commit.wait(timeout=10)
                        real_commit()
                        if lost_ack:
                            raise RuntimeError("simulated lost commit acknowledgement")

                    session.commit = paused_commit
                    yield session

            monkeypatch.setattr(provider_module, "SessionFactory", paused_factory)

            def mutate():
                with TestClient(create_app(), raise_server_exceptions=False) as client:
                    client.cookies.set("provider_session", old_session_id)
                    if operation == "replace":
                        response = client.post(
                            "/provider/session",
                            json={"bearer_token": new_secret, "ttl_seconds": 600},
                        )
                    else:
                        response = client.delete("/provider/session")
                    return response.status_code, client.cookies.get(
                        "provider_session", domain="testserver.local"
                    )

            def lookup_old():
                lookup_started.set()
                return provider_module.provider_sessions.get(old_session_id)

            with ThreadPoolExecutor(max_workers=2) as executor:
                mutation = executor.submit(mutate)
                try:
                    assert entered_commit.wait(timeout=10)
                    lookup = executor.submit(lookup_old)
                    assert lookup_started.wait(timeout=10)
                    with pytest.raises(TimeoutError):
                        lookup.result(timeout=0.1)
                finally:
                    release_commit.set()
                status, new_session_id = mutation.result(timeout=10)
                assert lookup.result(timeout=10) is None
            assert provider_module.provider_sessions.get(old_session_id) is None
            assert status == (500 if lost_ack else (201 if operation == "replace" else 204))
            if operation == "replace" and not lost_ack:
                assert new_session_id is not None
                assert provider_module.provider_sessions.get(new_session_id) == new_secret
    finally:
        release_commit.set()
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        get_settings.cache_clear()


def test_two_deletes_record_one_revocation_and_one_no_op(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    from research_agent.config.settings import get_settings

    get_settings.cache_clear()
    secret = "double-delete-" + uuid4().hex
    try:
        with TestClient(create_app()) as setup:
            created = setup.post(
                "/provider/session",
                json={"bearer_token": secret, "ttl_seconds": 600},
            )
            assert created.status_code == 201
            session_id = setup.cookies.get("provider_session")
            assert session_id is not None
            barrier = Barrier(2)

            def remove():
                with TestClient(create_app()) as client:
                    client.cookies.set("provider_session", session_id)
                    barrier.wait(timeout=10)
                    return client.delete("/provider/session").status_code

            with ThreadPoolExecutor(max_workers=2) as executor:
                assert list(executor.map(lambda _: remove(), range(2))) == [204, 204]
            assert provider_module.provider_sessions.get(session_id) is None
            with engine.connect() as connection:
                rows = connection.execute(
                    text(
                        "SELECT result, reason FROM provider_session_events "
                        "WHERE operation = 'DELETE'"
                    )
                ).all()
            assert set(rows) == {("accepted", "deleted"), ("no_op", "already_absent")}
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        get_settings.cache_clear()


def test_restart_does_not_restore_secret_from_durable_audit(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    from research_agent.config.settings import get_settings

    get_settings.cache_clear()
    secret = "restart-secret-" + uuid4().hex
    try:
        with TestClient(create_app()) as client:
            created = client.post(
                "/provider/session",
                json={"bearer_token": secret, "ttl_seconds": 600},
            )
            assert created.status_code == 201
            session_id = client.cookies.get("provider_session")
            assert session_id is not None
            assert provider_module.provider_sessions.get(session_id) == secret
            with engine.connect() as connection:
                assert connection.scalar(text("SELECT count(*) FROM provider_session_events")) == 1

            monkeypatch.setattr(provider_module, "provider_sessions", ProviderSessionStore())
            monkeypatch.setattr(
                reports_module, "provider_sessions", provider_module.provider_sessions
            )
            assert provider_module.provider_sessions.get(session_id) is None
            status = client.get("/provider/status")
            assert status.status_code == 200
            assert status.json()["credential_mode"] != "session_bearer_token"
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        get_settings.cache_clear()


def test_failed_replacement_stage_restores_old_session_and_cookie(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    from research_agent.config.settings import get_settings

    get_settings.cache_clear()
    first_secret = "first-stage-secret-" + uuid4().hex
    second_secret = "second-stage-secret-" + uuid4().hex
    try:
        with TestClient(create_app(), raise_server_exceptions=False) as client:
            created = client.post(
                "/provider/session",
                json={"bearer_token": first_secret, "ttl_seconds": 600},
            )
            assert created.status_code == 201
            old_session_id = client.cookies.get("provider_session")
            assert old_session_id is not None

            def fail_stage(*args, **kwargs):
                raise RuntimeError("injected audit stage failure")

            monkeypatch.setattr(audit_module.ProviderSessionAuditService, "stage", fail_stage)
            failed = client.post(
                "/provider/session",
                json={"bearer_token": second_secret, "ttl_seconds": 900},
            )
            assert failed.status_code == 500
            assert client.cookies.get("provider_session") == old_session_id
            assert provider_module.provider_sessions.get(old_session_id) == first_secret
            assert second_secret not in failed.text
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        get_settings.cache_clear()


def test_concurrent_replacement_and_delete_have_bounded_outcomes(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    from research_agent.config.settings import get_settings

    get_settings.cache_clear()
    old_secret = "concurrent-old-" + uuid4().hex
    replacement_secret = "concurrent-replacement-" + uuid4().hex
    try:
        with TestClient(create_app()) as setup:
            created = setup.post(
                "/provider/session",
                json={"bearer_token": old_secret, "ttl_seconds": 600},
            )
            assert created.status_code == 201
            old_session_id = setup.cookies.get("provider_session")
            assert old_session_id is not None

            barrier = Barrier(2)

            def replace() -> int:
                with TestClient(create_app()) as client:
                    client.cookies.set("provider_session", old_session_id)
                    barrier.wait()
                    return client.post(
                        "/provider/session",
                        json={"bearer_token": replacement_secret, "ttl_seconds": 900},
                    ).status_code

            def remove() -> int:
                with TestClient(create_app()) as client:
                    client.cookies.set("provider_session", old_session_id)
                    barrier.wait()
                    return client.delete("/provider/session").status_code

            with ThreadPoolExecutor(max_workers=2) as executor:
                statuses = list(executor.map(lambda task: task(), (replace, remove)))
            assert sorted(statuses) == [201, 204]
            assert provider_module.provider_sessions.get(old_session_id) is None
            audit = setup.get("/provider/audit")
            assert audit.status_code == 200
            assert all(old_secret not in str(event) for event in audit.json())
            assert all(replacement_secret not in str(event) for event in audit.json())
    finally:
        provider_module.provider_sessions.delete(
            old_session_id if "old_session_id" in locals() else None
        )
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        get_settings.cache_clear()


def test_concurrent_replacements_have_one_revoke_and_two_active_results(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    from research_agent.config.settings import get_settings

    get_settings.cache_clear()
    old_secret = "double-old-" + uuid4().hex
    replacement_secrets = ["double-one-" + uuid4().hex, "double-two-" + uuid4().hex]
    try:
        with TestClient(create_app()) as setup:
            created = setup.post(
                "/provider/session",
                json={"bearer_token": old_secret, "ttl_seconds": 600},
            )
            assert created.status_code == 201
            old_session_id = setup.cookies.get("provider_session")
            assert old_session_id is not None
            barrier = Barrier(2)

            def replace(secret: str) -> tuple[int, str | None]:
                with TestClient(create_app()) as client:
                    client.cookies.set("provider_session", old_session_id)
                    barrier.wait()
                    response = client.post(
                        "/provider/session",
                        json={"bearer_token": secret, "ttl_seconds": 900},
                    )
                    return response.status_code, client.cookies.get(
                        "provider_session", domain="testserver.local"
                    )

            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(replace, replacement_secrets))
            assert [result[0] for result in results] == [201, 201]
            assert provider_module.provider_sessions.get(old_session_id) is None
            assert all(
                session_id
                and provider_module.provider_sessions.get(session_id) in replacement_secrets
                for _, session_id in results
            )
            audit = setup.get("/provider/audit")
            assert audit.status_code == 200
            events = audit.json()
            assert [event["operation"] for event in events].count("DELETE") == 1
            assert [event["operation"] for event in events].count("CREATE") == 3
    finally:
        provider_module.provider_sessions.delete(
            old_session_id if "old_session_id" in locals() else None
        )
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        get_settings.cache_clear()


def test_provider_session_audit_read_enforces_read_audit(monkeypatch):
    def deny(session, capability):
        assert capability is SecurityCapability.READ_AUDIT
        raise SecurityCapabilityDenied("denied")

    monkeypatch.setattr(audit_module, "require_capability", deny)
    with TestClient(create_app()) as client:
        response = client.get("/provider/audit")
    assert response.status_code == 403
