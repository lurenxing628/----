"""Resource rail preferences stay usable when browser session storage fails."""

import json
import os
import subprocess
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_resource_rail_storage_failures_preserve_visible_controls():
    node, browser, modules = runtime_tools()
    result = subprocess.run(
        [node, str(Path(__file__).with_suffix(".cjs"))],
        env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
        capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["browser"].startswith("109.")
    assert report["cases"] == ["normal", "read-denied", "write-quota", "write-denied"]
    assert report["errors"] == report["external"] == []
    assert report["database"] is False and report["global_build"] is False
