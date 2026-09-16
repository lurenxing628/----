"""Current source + Chrome 109 + isolated real HTTP ledger; no global build."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_report_void_current_source_browser():
    node, browser, modules = runtime_tools()
    root = Path(__file__).resolve().parents[2]
    output = Path(tempfile.mkdtemp(prefix="aps-report-void-browser-"))
    result = subprocess.run([node, str(root / "tests/workbench/field_report_void_browser.cjs"), str(output)], cwd=str(root),
                            env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
                            capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr + "\n" + str(output)
    report = json.loads((output / "report-void-result.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.") and report["errors"] == []
    assert len(report["cases"]) == 5 and all(row["passed"] for row in report["cases"])
    assert report["production_db"] is False and report["global_build"] is False
    print("REPORT_VOID_BROWSER_ARTIFACTS " + str(output))
