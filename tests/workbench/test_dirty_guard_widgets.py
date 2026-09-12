"""Current-source guard and Modal behavior, without production database or build."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_dirty_guard_widgets():
    node, browser, modules = runtime_tools()
    root = Path(__file__).resolve().parents[2]
    output = Path(tempfile.mkdtemp(prefix="aps-dirty-guard-"))
    result = subprocess.run(
        [node, str(root / "tests/workbench/dirty_guard_probe.cjs"), str(output)],
        cwd=str(root), env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
        capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr + "\n" + str(output)
    report = json.loads((output / "dirty-guard-result.json").read_text(encoding="utf-8"))
    assert report["passed"] and len(report["cases"]) == 11
    assert not report["global_build"] and not report["database_access"]
    assert report["errors"] == [] and report["external"] == []
    assert report["browser"].startswith("109.")
    print("DIRTY_GUARD_ARTIFACTS " + str(output))
