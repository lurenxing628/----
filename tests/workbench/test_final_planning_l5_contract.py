"""One bounded contract run for the five authorized L5 frontend files."""

import json
import os
import subprocess
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_l5_overlap_and_trial_view_persistence_contracts():
    node, _, modules = runtime_tools()
    result = subprocess.run([node, str(Path(__file__).with_name("final_planning_l5_contract.cjs"))],
                            env=dict(os.environ, NODE_PATH=modules), capture_output=True,
                            text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["contract_only"] and not report["browser_or_full_entry_evidence"]
    assert not report["build_order_modified"] and report["compile_target"] == {"chrome": "109"}
    assert len(report["checks"]) >= 30
    print("L5_CONTRACT " + json.dumps(report, ensure_ascii=False), flush=True)
