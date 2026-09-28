"""Operator database configuration stays separate from the runtime engine."""

import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from research_agent import cli
from research_agent.config.settings import get_settings
from research_agent.persistence import database
from research_agent.persistence.owner_database import (
    OwnerDatabaseConfigurationError,
    create_owner_database_engine,
)


def test_owner_url_is_required_and_never_falls_back_to_runtime(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OWNER_DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://runtime:runtime-secret@localhost/runtime"
    )
    with pytest.raises(OwnerDatabaseConfigurationError, match="OWNER_DATABASE_URL") as missing:
        create_owner_database_engine()
    assert "runtime-secret" not in str(missing.value)


@pytest.mark.parametrize(
    "owner_url",
    [
        "invalid-secret-url",
        "sqlite:///local.db",
        "postgresql+psycopg:///missing-user",
        "postgresql+psycopg://owner:private-password@localhost",
    ],
)
def test_malformed_owner_url_is_redacted(monkeypatch, tmp_path, owner_url):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OWNER_DATABASE_URL", owner_url)
    with pytest.raises(OwnerDatabaseConfigurationError, match="OWNER_DATABASE_URL") as invalid:
        create_owner_database_engine()
    assert owner_url not in str(invalid.value)


def test_runtime_engine_uses_only_runtime_url_without_owner_setting(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OWNER_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://runtime:secret@localhost/runtime")
    get_settings.cache_clear()
    try:
        runtime = database.create_database_engine()
        try:
            assert runtime.url.username == "runtime"
            assert runtime.url.database == "runtime"
        finally:
            runtime.dispose()
    finally:
        get_settings.cache_clear()


def test_migration_cli_uses_owner_engine_and_disposes_it(monkeypatch):
    calls = []

    class OwnerEngine:
        def dispose(self):
            calls.append("dispose")

    owner = OwnerEngine()
    monkeypatch.setattr(cli, "create_owner_database_engine", lambda: owner)

    def migrations(engine):
        assert engine is owner
        calls.append("migrate")
        return []

    monkeypatch.setattr(cli, "run_migrations", migrations)
    monkeypatch.setattr(sys, "argv", ["research-agent", "migrate"])
    cli.main()
    assert calls == ["migrate", "dispose"]


def test_migration_cli_missing_owner_does_not_call_migrations(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OWNER_DATABASE_URL", raising=False)
    monkeypatch.setattr(cli, "run_migrations", lambda _: pytest.fail("runtime fallback"))
    monkeypatch.setattr(sys, "argv", ["research-agent", "migrate"])
    with pytest.raises(OwnerDatabaseConfigurationError, match="OWNER_DATABASE_URL"):
        cli.main()


def test_restore_cli_missing_owner_fails_before_reconstruction(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OWNER_DATABASE_URL", raising=False)
    script = Path(__file__).resolve().parents[2] / "scripts" / "restore_postgres.py"
    namespace = runpy.run_path(str(script))
    monkeypatch.setattr(sys, "argv", [str(script), str(tmp_path)])
    with pytest.raises(SystemExit) as failure:
        namespace["main"]()
    assert failure.value.code == 2
    assert "OWNER_DATABASE_URL" in capsys.readouterr().err


def test_backup_cli_uses_owner_engine_and_disposes_it(monkeypatch, tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts" / "backup_postgres.py"
    namespace = runpy.run_path(str(script))
    calls = []

    class OwnerEngine:
        def dispose(self):
            calls.append("dispose")

    owner = OwnerEngine()
    namespace["main"].__globals__["create_owner_database_engine"] = lambda: owner

    class Backup:
        def __init__(self, engine, *, pg_dump_path):
            assert engine is owner
            calls.append(("construct", pg_dump_path))

        def create(self, path, *, application_version, source_revision):
            calls.append(("create", path, application_version, source_revision))
            return SimpleNamespace(backup_id="backup", backup_directory=path)

    namespace["main"].__globals__["BackupCreationService"] = Backup
    destination = tmp_path / "backup"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(script),
            str(destination),
            "--application-version",
            "0.1.0",
            "--source-revision",
            "a1b2c3d",
        ],
    )
    namespace["main"]()
    assert calls == [
        ("construct", "pg_dump"),
        ("create", destination, "0.1.0", "a1b2c3d"),
        "dispose",
    ]
