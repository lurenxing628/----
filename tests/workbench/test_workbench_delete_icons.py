"""Every current deletion action uses one recognizable icon and visible text."""
import json
import subprocess
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_all_app_deletion_controls_use_trash_and_visible_text():
    node, _browser, _modules = runtime_tools()
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [node, str(root / "tests/workbench/deletion_icon_contract.cjs")],
        cwd=str(root), capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["scope"] == "current-app-deletion-action-inventory"
    assert len(report["inventory"]) >= 17
