"""Current batch supplier editor in Chromium 109; component I/O is explicitly mocked."""

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_batch_merged_supplier_readonly_and_separate_update():
    node, browser, modules = runtime_tools()
    root = Path(__file__).resolve().parents[2]
    output = Path(tempfile.mkdtemp(prefix="aps-batch-merged-supplier-"))
    result = subprocess.run(
        [node, str(Path(__file__).with_name("batch_merged_supplier_probe.cjs")), str(output)],
        cwd=str(root), env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
        capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr + "\n" + str(output)
    report = json.loads((output / "batch-merged-supplier-result.json").read_text(encoding="utf-8"))
    assert report["scope"] == "batch-merged-supplier-component-mock"
    assert not report["production_persistence_tested"] and not report["compile"]["global_build"]
    assert report["browser"].startswith("109.") and report["compile"]["target"] == {"chrome": "109"}
    assert len(report["cases"]) == 16 and all(case["passed"] for case in report["cases"])
    assert len(report["screenshots"]) == 16
    assert report["errors"] == [] and report["external"] == []
    for source in report["sources"]:
        assert hashlib.sha256((root / source["path"]).read_bytes()).hexdigest() == source["sha256"]
    print("BATCH_MERGED_SUPPLIER_ARTIFACTS " + str(output), flush=True)
