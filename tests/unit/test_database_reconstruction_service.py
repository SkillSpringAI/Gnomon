"""M2.5 reconstruction command boundary and credential handling."""

from pathlib import Path

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
    args, env = service._pg_restore_command(dump)
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
    assert "--exclude-table-data=research_agent_schema_migrations" in args
    assert "--exclude-table-data=security_state" in args
    assert "secret" not in args
    assert str(dump) == args[-1]
    assert env["PGPASSWORD"] == "secret"
    assert "DATABASE_URL" not in env


def test_pg_restore_command_requires_postgresql():
    service = DatabaseReconstructionService(engine("sqlite:///local.db"))
    with pytest.raises(DatabaseReconstructionError, match="PostgreSQL"):
        service._pg_restore_command(Path("database.dump"))
