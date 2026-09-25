"""Operator entry point for M2.5 PostgreSQL reconstruction."""

from argparse import ArgumentParser
from pathlib import Path

from research_agent.application.database_reconstruction_service import (
    DatabaseReconstructionError,
    DatabaseReconstructionService,
)
from research_agent.persistence.database import engine


def main() -> int:
    parser = ArgumentParser(description="Reconstruct a PostgreSQL target from a backup set.")
    parser.add_argument("backup_directory", type=Path)
    parser.add_argument("--pg-restore", default="pg_restore")
    args = parser.parse_args()
    try:
        result = DatabaseReconstructionService(
            engine,
            pg_restore_path=args.pg_restore,
        ).reconstruct(args.backup_directory)
    except DatabaseReconstructionError as exc:
        parser.error(str(exc))
    print(f"Reconstructed {result.target_database_scope} from {result.backup_directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
