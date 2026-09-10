"""Current-source workspaces in the app shell, without an inherited plana scope."""

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_workspace_primitive_styles_chrome109():
    node, browser, modules = runtime_tools()
    root = Path(__file__).resolve().parents[2]
    output = Path(tempfile.mkdtemp(prefix="aps-workspace-primitives-ah-"))
    print("WORKSPACE_PRIMITIVE_ARTIFACTS " + str(output), flush=True)
    result = subprocess.run(
        [node, str(root / "tests/workbench/workspace_primitive_styles_probe.cjs"), str(output)],
        cwd=str(root), env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
        capture_output=True, text=True, timeout=240,
    )
    assert result.returncode == 0, result.stdout + result.stderr + "\n" + str(output)
    report = json.loads((output / "primitive-styles-result.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.")
    assert report["compile"]["global_build"] is False
    assert report["production_persistence_tested"] is False
    assert report["errors"] == [] and report["external"] == []
    assert len(report["cases"]) == 8 and all(row["passed"] for row in report["cases"])
    assert len(report["legacy_checks"]) == 8
    assert len(report["negative_controls"]) == 2
    assert len(report["screenshots"]) == 40
    for source in report["sources"]:
        assert hashlib.sha256((root / source["path"]).read_bytes()).hexdigest() == source["sha256"]
    print("WORKSPACE_PRIMITIVE_VERIFIED " + str(output), flush=True)
