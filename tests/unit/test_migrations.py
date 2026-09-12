from pathlib import Path

from research_agent.application.migrations import migration_files


def test_migration_files_are_numbered_and_ordered(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("ignored", encoding="utf-8")
    (tmp_path / "002_second.sql").write_text("select 2", encoding="utf-8")
    (tmp_path / "001_first.sql").write_text("select 1", encoding="utf-8")
    (tmp_path / "notes.sql").write_text("ignored", encoding="utf-8")

    assert [path.name for path in migration_files(tmp_path)] == [
        "001_first.sql",
        "002_second.sql",
    ]
