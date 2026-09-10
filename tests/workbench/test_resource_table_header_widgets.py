"""Chromium 109 component fixtures, not full integration or database proof."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_live_browser import runtime_tools


def test_resource_table_header_widgets():
    node, browser, modules = runtime_tools()
    output = Path(tempfile.mkdtemp(prefix="aps-resource-table-header-"))
    process = subprocess.run(
        [node, str(HERE / "resource_table_header_probe.cjs"), str(output)],
        cwd=str(HERE.parent.parent),
        env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
        capture_output=True, text=True, timeout=240,
    )
    assert process.returncode == 0, process.stdout + process.stderr + "\n" + str(output)
    report = json.loads((output / "table-header-result.json").read_text(encoding="utf-8"))
    assert report["scope"] == "isolated-component-fixtures"
    assert report["browser"].startswith("109.")
    assert len(report["cases"]) == 60 and all(row["passed"] for row in report["cases"])
    assert len(report["screenshots"]) == 28
    assert not report["errors"] and not report["external"]
    assert report["source_hashes_still_match"]
    print("RESOURCE_TABLE_HEADER_ARTIFACTS " + str(output), flush=True)
