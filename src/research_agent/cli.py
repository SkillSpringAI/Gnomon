"""Command-line entry point."""

import argparse

from research_agent.application.migrations import run_migrations
from research_agent.persistence.database import engine


def main() -> None:
    """Run the command-line entry point."""
    parser = argparse.ArgumentParser(prog="research-agent")
    parser.add_argument("command", nargs="?", choices=("migrate",))
    args = parser.parse_args()
    if args.command == "migrate":
        applied = run_migrations(engine)
        print(f"Applied {len(applied)} migration(s): {', '.join(applied) or 'none'}")
        return
    print("research-agent: use `python -m uvicorn research_agent.api.app:app --reload`")


if __name__ == "__main__":
    main()
