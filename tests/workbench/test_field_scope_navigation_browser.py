"""A dashboard task anchor must not follow a later task's successful report save."""

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_task_switch_save_rebinds_operation_and_preserves_plan_scope():
    node, browser, modules = runtime_tools()
    here = Path(__file__).resolve().parent
    output = Path(tempfile.mkdtemp(prefix="aps-field-scope-navigation-"))
    print("FIELD_SCOPE_NAVIGATION_ARTIFACTS " + str(output), flush=True)
    result = subprocess.run(
        [node, str(here / "field_scope_navigation_browser.cjs"), str(output)],
        cwd=str(here.parent.parent),
        env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr + "\n" + str(output)
    report = json.loads((output / "field-scope-navigation.json").read_text())
    assert report["completed"] is True and len(report["cases"]) == 5
    assert report["browser"].startswith("109.")
    assert report["errors"] == [] and report["http_errors"] == []
    assert report["production_db"] is False and report["global_build"] is False
    assert len(report["writes"]) == 3
    for row in report["sources"]:
        assert hashlib.sha256((here.parent.parent / row["path"]).read_bytes()).hexdigest() == row["sha256"], row["path"]
