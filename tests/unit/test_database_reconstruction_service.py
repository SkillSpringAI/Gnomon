"""M2.5 reconstruction command boundary and credential handling."""

from pathlib import Path
from subprocess import CompletedProcess

import pytest
from sqlalchemy import create_engine

from research_agent.application.database_reconstruction_service import (
    DatabaseReconstructionError,
    DatabaseReconstructionService,
)


def engine(url: str = "postgresql+psycopg://research_agent:secret@localhost:5432/db"):
    return create_engine(url)


def test_pg_restore_command_uses_supported_flags_and_excludes_bootstrap_data(tmp_path):
    dump = tmp_path / "database.dump"
    dump.write_bytes(b"dump")
    service = DatabaseReconstructionService(
        engine(),
        pg_restore_path="pg_restore-test",
        environment={"PATH": "test", "DATABASE_URL": "postgresql://leak"},
    )
    restore_list = tmp_path / "restore.list"
    args, env = service._pg_restore_command(dump, restore_list)
    assert args[:9] == [
        "pg_restore-test",
        "--data-only",
        "--single-transaction",
        "--exit-on-error",
        "--no-owner",
        "--no-privileges",
        "--dbname",
        "db",
        "--no-password",
    ]
    assert args[9:11] == ["--use-list", str(restore_list)]
    assert "secret" not in args
    assert str(dump) == args[-1]
    assert env["PGPASSWORD"] == "secret"
    assert "DATABASE_URL" not in env


def test_pg_restore_command_requires_postgresql():
    service = DatabaseReconstructionService(engine("sqlite:///local.db"))
    with pytest.raises(DatabaseReconstructionError, match="PostgreSQL"):
        service._pg_restore_command(Path("database.dump"), Path("restore.list"))


def test_restore_list_excludes_protected_data_and_orders_foreign_keys(tmp_path, monkeypatch):
    dump = tmp_path / "database.dump"
    listing = (
        "; archive header\n"
        "1; 0 101 TABLE DATA public research_agent_schema_migrations owner\n"
        "2; 0 102 TABLE DATA public security_state owner\n"
        "3; 0 103 TABLE DATA public research_tasks owner\n"
        "4; 0 104 TABLE DATA public trusted_sources owner\n"
        "5; 0 105 TABLE public security_state owner\n"
        "6; 0 106 TABLE DATA public assessment_evidence owner\n"
        "7; 0 107 TABLE DATA public hypothesis_assessments owner\n"
    )

    def runner(args, *, env, cwd=None):
        assert args == ["pg_restore", "--list", str(dump)]
        assert "DATABASE_URL" not in env
        return CompletedProcess(args, 0, listing, "")

    service = DatabaseReconstructionService(
        engine(), runner=runner, environment={"DATABASE_URL": "secret"}
    )
    monkeypatch.setattr(
        service,
        "_table_dependencies",
        lambda: [("assessment_evidence", "hypothesis_assessments")],
    )
    restore_list = tmp_path / "restore.list"
    service._write_restore_list(dump, restore_list)
    selected = restore_list.read_text(encoding="utf-8")
    assert ";1; 0 101 TABLE DATA public research_agent_schema_migrations" in selected
    assert ";2; 0 102 TABLE DATA public security_state" in selected
    assert "3; 0 103 TABLE DATA public research_tasks" in selected
    assert "4; 0 104 TABLE DATA public trusted_sources" in selected
    assert "5; 0 105 TABLE public security_state" in selected
    assert selected.index("7; 0 107 TABLE DATA") < selected.index("6; 0 106 TABLE DATA")


def test_reconstruct_composes_mechanics_then_recovery(tmp_path, monkeypatch):
    service = DatabaseReconstructionService(engine())
    mechanical = object()
    recovered = object()
    calls = []

    def restore(directory):
        calls.append(("mechanics", directory))
        return mechanical

    def enter(result):
        calls.append(("recovery", result))
        return recovered

    monkeypatch.setattr(service, "_restore_verified_data", restore)
    monkeypatch.setattr(service, "_enter_recovery", enter)
    assert service.reconstruct(tmp_path) is recovered
    assert calls == [("mechanics", tmp_path), ("recovery", mechanical)]


def test_public_restore_cli_calls_complete_workflow_only(tmp_path, monkeypatch, capsys):
    import runpy
    import sys
    from types import SimpleNamespace

    script = Path(__file__).resolve().parents[2] / "scripts" / "restore_postgres.py"
    namespace = runpy.run_path(str(script))
    calls = []

    class Service:
        def __init__(self, target, *, pg_restore_path):
            calls.append(("construct", pg_restore_path))

        def reconstruct(self, directory):
            calls.append(("reconstruct", directory))
            return SimpleNamespace(
                target_database_scope="target",
                backup_directory=directory,
                recovery_context_id="fresh-context",
            )

    namespace["main"].__globals__["DatabaseReconstructionService"] = Service
    monkeypatch.setattr(sys, "argv", [str(script), str(tmp_path), "--pg-restore", "restore"])
    assert namespace["main"]() == 0
    assert calls == [("construct", "restore"), ("reconstruct", tmp_path)]
    assert "fresh-context" in capsys.readouterr().out
    for flag in ("--skip-recovery", "--restore-only"):
        monkeypatch.setattr(sys, "argv", [str(script), str(tmp_path), flag])
        with pytest.raises(SystemExit) as exc:
            namespace["main"]()
        assert exc.value.code == 2
    assert len(calls) == 2
