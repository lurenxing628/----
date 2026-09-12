"""Current shared components in actual Chromium 109; no build or production writes."""
import json
import os
import subprocess
import tempfile
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_shared_controls_widgets():
    node, browser, modules = runtime_tools()
    output = Path(tempfile.mkdtemp(prefix="aps-workbench-shared-controls-"))
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [node, str(root / "tests/workbench/shared_controls_probe.cjs"), str(output)],
        cwd=str(root), env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
        capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr + "\nArtifacts: " + str(output)
    report = json.loads((output / "shared-controls-result.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.")
    assert len(report["cases"]) == 11
    assert report["errors"] == report["external"] == []
    assert all(row["passed"] for row in report["cases"])
    print("SHARED_CONTROLS_ARTIFACTS " + str(output), flush=True)
