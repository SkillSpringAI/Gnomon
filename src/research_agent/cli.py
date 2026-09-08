"""Command-line entry point."""


def main() -> None:
    """Run the command-line entry point."""
    print("research-agent: use `python -m uvicorn research_agent.api.app:app --reload`")


if __name__ == "__main__":
    main()
