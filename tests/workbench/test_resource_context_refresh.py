"""Parent resource edits refresh once, retain user edits, and keep concurrent guards."""

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_parent_refresh_and_own_catalog_commit_preserve_draft():
    node, browser, modules = runtime_tools()
    root = Path(__file__).resolve().parents[2]
    output = Path(tempfile.mkdtemp(prefix="aps-resource-context-refresh-"))
    print("RESOURCE_CONTEXT_REFRESH_ARTIFACTS " + str(output), flush=True)
    result = subprocess.run(
        [node, str(root / "tests/workbench/resource_context_refresh_probe.cjs"), str(output)],
        cwd=str(root), env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
        capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr + "\n" + str(output)
    report = json.loads((output / "resource-context-refresh.json").read_text())
    assert report["completed"] is True and len(report["cases"]) == 3
    assert report["browser"].startswith("109.") and report["errors"] == []
    assert report["production_db"] is False and report["global_build"] is False
    for row in report["sources"]:
        assert hashlib.sha256((root / row["path"]).read_bytes()).hexdigest() == row["sha256"], row["path"]
