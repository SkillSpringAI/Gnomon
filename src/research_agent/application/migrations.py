"""Apply ordered PostgreSQL migrations and record their completion."""

from pathlib import Path

from sqlalchemy import Engine, text

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"
MIGRATIONS_TABLE = "research_agent_schema_migrations"


def migration_files(directory: Path = MIGRATIONS_DIR) -> list[Path]:
    """Return numbered SQL migrations in deterministic order."""
    return sorted(path for path in directory.glob("[0-9][0-9][0-9]_*.sql") if path.is_file())


def run_migrations(engine: Engine, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply pending migrations and return the versions applied this run."""
    files = migration_files(directory)
    applied: list[str] = []
    with engine.begin() as connection:
        connection.execute(
            text(
                f"CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE} ("
                "version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now()"
                ")"
            )
        )
    for path in files:
        version = path.name
        with engine.begin() as connection:
            connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtext('research-agent-migrations'))")
            )
            known = connection.scalar(
                text(f"SELECT 1 FROM {MIGRATIONS_TABLE} WHERE version = :version"),
                {"version": version},
            )
            if known is not None:
                continue
            connection.exec_driver_sql(path.read_text(encoding="utf-8"))
            connection.execute(
                text(f"INSERT INTO {MIGRATIONS_TABLE} (version) VALUES (:version)"),
                {"version": version},
            )
            applied.append(version)
    return applied
