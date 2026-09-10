"""Current-source component mock in installed Chrome109; no global build."""

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_batch_components_chrome109():
    node, browser, modules = runtime_tools()
    root = Path(__file__).resolve().parents[2]
    output = Path(tempfile.mkdtemp(prefix="aps-batch-widgets-"))
    result = subprocess.run([node, str(root / "tests/workbench/batch_widgets_probe.cjs"), str(output)], cwd=str(root),
        env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser), capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr + "\n" + str(output)
    report = json.loads((output / "batch-result.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.") and report["compile"]["global_build"] is False
    assert report["errors"] == [] and report["external"] == []
    assert len(report["cases"]) == 32 and all(row["passed"] for row in report["cases"])
    assert len(report["screenshots"]) == 40
    for source in report["sources"]:
        assert hashlib.sha256((root / source["path"]).read_bytes()).hexdigest() == source["sha256"]
    print("BATCH_WIDGET_ARTIFACTS " + str(output))
