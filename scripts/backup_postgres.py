"""Create a supported PostgreSQL dump and manifest backup set."""

import argparse
from pathlib import Path

from sqlalchemy import create_engine

from research_agent.application.backup_creation_service import BackupCreationService
from research_agent.config.settings import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup_directory", type=Path)
    parser.add_argument("--application-version", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--pg-dump", default="pg_dump")
    args = parser.parse_args()

    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        result = BackupCreationService(engine, pg_dump_path=args.pg_dump).create(
            args.backup_directory,
            application_version=args.application_version,
            source_revision=args.source_revision,
        )
        print(f"Created backup {result.backup_id} at {result.backup_directory}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
