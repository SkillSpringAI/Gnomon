"""M2.11 credential exclusion across backup material and reconstructed data."""

import shutil
import subprocess
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from m2_reconstruction_fixture import (
    CANONICAL_RECONSTRUCTION_TABLES,
    seed_canonical_reconstruction_fixture,
)
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from research_agent.api.app import create_app
from research_agent.api.routes import provider as provider_module
from research_agent.application.backup_creation_service import BackupCreationService
from research_agent.application.database_reconstruction_service import DatabaseReconstructionService
from research_agent.application.migrations import run_migrations
from research_agent.application.provider_session import ProviderSessionStore
from research_agent.application.research_service import InMemoryResearchTaskRepository
from research_agent.config.settings import Settings, get_settings

SOURCE_REVISION = "316c90bf1816743ce73571e907b5c24e4da6cdec"


def _persisted_text(db) -> dict[str, str]:
    """Cover every column, including JSON command and audit metadata."""
    with db.connect() as conn:
        names = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = current_schema() AND table_type = 'BASE TABLE'"
            )
        ).scalars()
        result: dict[str, str] = {}
        for name in names:
            quoted = '"' + str(name).replace('"', '""') + '"'
            result[str(name)] = "\n".join(
                conn.execute(text(f"SELECT row_to_json(t)::text FROM {quoted} AS t")).scalars()
            )
        return result


def test_database_password_is_process_only_when_constructing_backup_commands(tmp_path):
    sentinel = "m2-db-password-" + uuid4().hex
    url = make_url(get_settings().database_url).set(password=sentinel)
    fake_engine = create_engine(url)
    try:
        backup = BackupCreationService(
            fake_engine,
            environment={"DATABASE_URL": url.render_as_string(hide_password=False)},
        )
        dump_args, dump_env = backup._pg_dump_command(tmp_path / "database.dump")
        restore = DatabaseReconstructionService(
            fake_engine,
            environment={"DATABASE_URL": url.render_as_string(hide_password=False)},
        )
        restore_args, restore_env = restore._pg_restore_command(
            tmp_path / "database.dump", tmp_path / "restore.list"
        )
        for args, env in ((dump_args, dump_env), (restore_args, restore_env)):
            assert sentinel not in " ".join(args)
            assert "DATABASE_URL" not in env
            assert env["PGPASSWORD"] == sentinel
    finally:
        fake_engine.dispose()


@pytest.mark.skipif(
    shutil.which("pg_dump") is None or shutil.which("pg_restore") is None,
    reason="pg_dump and pg_restore are not installed",
)
def test_credential_sentinels_absent_after_real_backup_and_restore(tmp_path, monkeypatch):
    base_url = make_url(get_settings().database_url)
    if base_url.host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("credential drill requires local PostgreSQL")
    source_name = "credential_source_" + uuid4().hex
    target_name = "credential_target_" + uuid4().hex
    admin = create_engine(base_url, isolation_level="AUTOCOMMIT")
    source = create_engine(base_url.set(database=source_name))
    target = create_engine(base_url.set(database=target_name))
    created: list[str] = []
    aws_key = "m2-aws-key-" + uuid4().hex
    aws_secret = "m2-aws-secret-" + uuid4().hex
    aws_session = "m2-aws-session-" + uuid4().hex
    aws_bearer = "m2-aws-bearer-" + uuid4().hex
    provider_token = "m2-provider-session-" + uuid4().hex
    database_url_secret = "m2-database-url-" + uuid4().hex
    sentinels = (
        aws_key,
        aws_secret,
        aws_session,
        aws_bearer,
        provider_token,
        database_url_secret,
    )
    try:
        try:
            with admin.connect() as conn:
                for name in (source_name, target_name):
                    conn.exec_driver_sql(f'CREATE DATABASE "{name}"')
                    created.append(name)
        except SQLAlchemyError as exc:
            pytest.skip(f"cannot create disposable databases: {exc}")
        run_migrations(source)
        run_migrations(target)
        with source.begin() as conn:
            seed_canonical_reconstruction_fixture(conn, variant="baseline")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", aws_key)
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", aws_secret)
        monkeypatch.setenv("AWS_SESSION_TOKEN", aws_session)
        monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)
        monkeypatch.setenv(
            "DATABASE_URL",
            base_url.set(password=database_url_secret).render_as_string(
                hide_password=False
            ),
        )
        monkeypatch.setattr(
            provider_module,
            "get_settings",
            lambda: Settings(
                llm_provider="bedrock",
                environment="local",
                persistence_backend="postgres",
                database_url=source.url.render_as_string(hide_password=False),
            ),
        )
        monkeypatch.setattr(provider_module, "SessionFactory", sessionmaker(bind=source))
        sessions = ProviderSessionStore()
        monkeypatch.setattr(provider_module, "provider_sessions", sessions)
        with TestClient(create_app(repository=InMemoryResearchTaskRepository())) as client:
            chain_status = client.get("/provider/status")
            assert chain_status.status_code == 200
            assert chain_status.json()["credential_mode"] == "aws_default_chain"
            assert aws_key not in chain_status.text
            assert aws_secret not in chain_status.text
            monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", aws_bearer)
            bearer_status = client.get("/provider/status")
            assert bearer_status.status_code == 200
            assert bearer_status.json()["credential_mode"] == "bearer_token"
            assert aws_bearer not in bearer_status.text
            created_session = client.post(
                "/provider/session",
                json={"bearer_token": provider_token, "ttl_seconds": 600},
            )
            assert created_session.status_code == 201
            assert provider_token not in created_session.text
            session_id = client.cookies.get("provider_session")
            assert sessions.get(session_id) == provider_token
            audit = client.get("/provider/audit")
            assert audit.status_code == 200
            assert provider_token not in audit.text
        source_rows = _persisted_text(source)
        assert set(CANONICAL_RECONSTRUCTION_TABLES).issubset(source_rows)
        assert all(source_rows[name] for name in CANONICAL_RECONSTRUCTION_TABLES)
        for name, rows in source_rows.items():
            assert all(secret not in rows for secret in sentinels), name

        backup = BackupCreationService(source).create(
            tmp_path / "backup-set",
            application_version="0.1.0",
            source_revision=SOURCE_REVISION,
        )
        manifest_text = backup.manifest_path.read_text(encoding="utf-8")
        dump_bytes = backup.dump_path.read_bytes()
        archive_sql = subprocess.run(
            ["pg_restore", "--data-only", "--file=-", str(backup.dump_path)],
            check=True,
            capture_output=True,
        ).stdout
        for secret in sentinels:
            assert secret not in manifest_text
            assert secret.encode() not in dump_bytes
            assert secret.encode() not in archive_sql

        restored = DatabaseReconstructionService(target).reconstruct(backup.backup_directory)
        assert restored.recovery_context_id is not None
        target_rows = _persisted_text(target)
        assert set(CANONICAL_RECONSTRUCTION_TABLES).issubset(target_rows)
        assert all(target_rows[name] for name in CANONICAL_RECONSTRUCTION_TABLES)
        for name, rows in target_rows.items():
            assert all(secret not in rows for secret in sentinels), name
    finally:
        source.dispose()
        target.dispose()
        for name in reversed(created):
            with admin.connect() as conn:
                conn.exec_driver_sql(f'DROP DATABASE "{name}" WITH (FORCE)')
        admin.dispose()
