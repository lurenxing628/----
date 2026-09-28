"""Real Chromium 109 stage management; persistence is tested by group API tests."""

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_group_creation_split_release_supplier_and_cycle_widgets():
    node, browser, modules = runtime_tools()
    root = Path(__file__).resolve().parents[2]
    output = Path(tempfile.mkdtemp(prefix="aps-process-group-"))
    result = subprocess.run(
        [node, str(Path(__file__).with_name("process_group_widgets_probe.cjs")), str(output)],
        cwd=str(root), env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
        capture_output=True, text=True, timeout=240,
    )
    assert result.returncode == 0, result.stdout + result.stderr + "\n" + str(output)
    report = json.loads((output / "process-group-result.json").read_text(encoding="utf-8"))
    assert report["scope"] == "process-group-component"
    assert not report["production_persistence_tested"] and not report["compile"]["global_build"]
    assert report["compile"]["target"] == {"chrome": "109"}
    assert len(report["cases"]) == 24 and all(row["passed"] for row in report["cases"])
    assert report["errors"] == [] and report["external"] == []
    assert len(report["screenshots"]) == 4
    for source in report["sources"]:
        assert hashlib.sha256((root / source["path"]).read_bytes()).hexdigest() == source["sha256"]
    print("PROCESS_GROUP_ARTIFACTS " + str(output), flush=True)
