"""Real Chromium 109 for the current supplier selector, with explicit mock I/O."""

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_supplier_choices_group_scope_and_error_location():
    node, browser, modules = runtime_tools()
    root = Path(__file__).resolve().parents[2]
    output = Path(tempfile.mkdtemp(prefix="aps-source-supplier-"))
    result = subprocess.run(
        [node, str(Path(__file__).with_name("process_source_supplier_probe.cjs")), str(output)],
        cwd=str(root), env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
        capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr + "\n" + str(output)
    report = json.loads((output / "source-supplier-result.json").read_text(encoding="utf-8"))
    assert report["scope"] == "process-source-supplier-component"
    assert not report["production_persistence_tested"] and not report["compile"]["global_build"]
    assert report["compile"]["target"] == {"chrome": "109"}
    assert len(report["cases"]) == 20 and all(row["passed"] for row in report["cases"])
    assert report["errors"] == [] and report["external"] == []
    assert len(report["screenshots"]) == 4
    for source in report["sources"]:
        assert hashlib.sha256((root / source["path"]).read_bytes()).hexdigest() == source["sha256"]
    print("SOURCE_SUPPLIER_ARTIFACTS " + str(output), flush=True)
