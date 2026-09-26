"""Native Chrome 109 PDF printing over current plan components, with no real DB."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_plan_print_prepares_all_rows_and_restores_screen(tmp_path):
    node, browser, modules = runtime_tools()
    root = Path(__file__).resolve().parents[2]
    output = tmp_path / "plan-print"
    result = subprocess.run(
        [node, str(root / "tests/workbench/test_plan_print.cjs"), str(output)],
        cwd=str(root), env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
        capture_output=True, text=True, timeout=120,
    )
    report = json.loads((output / "plan-print-result.json").read_text(encoding="utf-8"))
    assert result.returncode == 0, result.stdout + result.stderr + report.get("failure", "")
    assert report["browser"].startswith("109.")
    assert len(report["cases"]) == 5
    assert report["production_persistence_tested"] is False
    for row in report["cases"]:
        assert Path(row["pdf"]).read_bytes().startswith(b"%PDF-")
        assert row["after"] == row["before"]
    for source in report["sources"]:
        assert hashlib.sha256((root / source["path"]).read_bytes()).hexdigest() == source["sha256"]
