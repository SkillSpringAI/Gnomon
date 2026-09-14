"""Apply ordered PostgreSQL migrations and record their completion."""

import hashlib
from pathlib import Path

from sqlalchemy import Engine, text

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"
MIGRATIONS_TABLE = "research_agent_schema_migrations"


def migration_files(directory: Path = MIGRATIONS_DIR) -> list[Path]:
    """Return numbered SQL migrations in deterministic order."""
    return sorted(path for path in directory.glob("[0-9][0-9][0-9]_*.sql") if path.is_file())


def migration_checksum(path: Path) -> str:
    """Return the stable digest recorded for an applied migration."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_migrations(engine: Engine, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply pending migrations and return the versions applied this run."""
    files = migration_files(directory)
    applied: list[str] = []
    with engine.begin() as connection:
        connection.execute(
            text(
                f"CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE} ("
                "version TEXT PRIMARY KEY, checksum TEXT, "
                "applied_at TIMESTAMPTZ NOT NULL DEFAULT now()"
                ")"
            )
        )
        connection.execute(
            text(
                f"ALTER TABLE {MIGRATIONS_TABLE} "
                "ADD COLUMN IF NOT EXISTS checksum TEXT"
            )
        )
    for path in files:
        version = path.name
        with engine.begin() as connection:
            connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtext('research-agent-migrations'))")
            )
            known = connection.execute(
                text(f"SELECT checksum FROM {MIGRATIONS_TABLE} WHERE version = :version"),
                {"version": version},
            ).first()
            checksum = migration_checksum(path)
            if known is not None:
                if known[0] is not None and known[0] != checksum:
                    raise RuntimeError(f"Applied migration content changed: {version}")
                if known[0] is None:
                    connection.execute(
                        text(
                            f"UPDATE {MIGRATIONS_TABLE} SET checksum = :checksum "
                            "WHERE version = :version"
                        ),
                        {"version": version, "checksum": checksum},
                    )
                continue
            connection.exec_driver_sql(path.read_text(encoding="utf-8"))
            connection.execute(
                text(
                    f"INSERT INTO {MIGRATIONS_TABLE} (version, checksum) "
                    "VALUES (:version, :checksum)"
                ),
                {"version": version, "checksum": checksum},
            )
            applied.append(version)
    return applied
