from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_dashboard_workspace_uses_dedicated_action_grid() -> None:
    css = _read("static/css/ui_contract.css")
    assert ".aps-workspace-actions" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in css
    assert ".aps-workspace-actions .btn:last-child:nth-child(odd)" in css

    for rel_path in ("templates/dashboard.html", "web_new_test/templates/dashboard.html"):
      source = _read(rel_path)
      workspace_start = source.index("常用工作区")
      workspace_source = source[workspace_start:]
      assert "aps-workspace-actions" in workspace_source
      assert "action-bar-flat" not in workspace_source
      assert "'schedule'" not in workspace_source
      assert "'chart'" not in workspace_source


def main() -> None:
    test_dashboard_workspace_uses_dedicated_action_grid()
    print("OK")


if __name__ == "__main__":
    main()
