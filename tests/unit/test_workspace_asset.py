"""Check the packaged workspace asset and its state guards."""

from pathlib import Path


def test_workspace_asset_is_packaged_and_state_driven() -> None:
    asset = (
        Path(__file__).parents[2]
        / "src"
        / "research_agent"
        / "api"
        / "routes"
        / "workspace.html"
    )
    content = asset.read_text(encoding="utf-8")
    assert "__TASK_ID__" in content
    assert "report?.task_status === 'active'" in content
    assert "running || !planned" in content
    assert "The investigation changed" in content
    assert "displayed history may be stale" in content
    assert "textContent" in content
