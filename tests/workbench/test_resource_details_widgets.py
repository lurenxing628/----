"""Real Chromium 109 with read-only component mocks, not database proof."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_live_browser import runtime_tools


def test_resource_detail_navigation_and_controls():
    node, browser, modules = runtime_tools()
    output = Path(tempfile.mkdtemp(prefix="aps-resource-details-"))
    result = subprocess.run(
        [node, str(HERE / "resource_details_probe.cjs"), str(output)],
        cwd=str(HERE.parent.parent), env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
        capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr + "\n" + str(output)
    report = json.loads((output / "details-result.json").read_text(encoding="utf-8"))
    assert report["scope"] == "read-only-component-mock"
    assert report["browser"].startswith("109.")
    assert len(report["cases"]) == 24 and all(row["passed"] for row in report["cases"])
    assert not report["errors"] and not report["external"]
    print("RESOURCE_DETAILS_ARTIFACTS " + str(output), flush=True)
