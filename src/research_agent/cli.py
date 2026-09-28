"""Command-line entry point."""

import argparse

from research_agent.application.migrations import run_migrations
from research_agent.persistence.owner_database import create_owner_database_engine


def main() -> None:
    """Run the command-line entry point."""
    parser = argparse.ArgumentParser(prog="research-agent")
    parser.add_argument("command", nargs="?", choices=("migrate",))
    args = parser.parse_args()
    if args.command == "migrate":
        engine = create_owner_database_engine()
        try:
            applied = run_migrations(engine)
        finally:
            engine.dispose()
        print(f"Applied {len(applied)} migration(s): {', '.join(applied) or 'none'}")
        return
    print("research-agent: use `python -m uvicorn research_agent.api.app:app --reload`")


if __name__ == "__main__":
    main()
