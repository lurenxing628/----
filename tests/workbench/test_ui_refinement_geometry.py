"""Independent Chromium 109 positive and negative controls for UI evidence probes."""

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_ui_refinement_geometry_detects_local_failures_in_chromium109():
    node, browser, modules = runtime_tools()
    root = Path(__file__).resolve().parents[2]
    output = Path(tempfile.mkdtemp(prefix="aps-ui-refinement-geometry-"))
    print("UI_GEOMETRY_CONTRACT_ARTIFACTS " + str(output), flush=True)
    result = subprocess.run(
        [node, str(root / "tests/workbench/ui_refinement_geometry_test.cjs"), str(output)],
        cwd=str(root), env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
        capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr + "\nArtifacts: " + str(output)
    report = json.loads((output / "geometry-contract-results.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.")
    assert report["production_data_tested"] is False
    assert report["errors"] == []
    assert len(report["cases"]) == 38 and all(row["passed"] for row in report["cases"])
    assert {row["viewport"]["width"] for row in report["cases"]} == {1366, 1280}
    for row in report["cases"]:
        assert (output / row["screenshot"]).is_file()
    for source in report["sources"]:
        assert hashlib.sha256((root / source["file"]).read_bytes()).hexdigest() == source["sha256"]
