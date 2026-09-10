"""Current-source process collection widgets; mock API, not persistence proof."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_live_browser import runtime_tools


def test_process_actions_contract():
    node, _, modules = runtime_tools()
    result = subprocess.run([node, str(HERE / "process_actions_contract_probe.cjs")],
                            env=dict(os.environ, NODE_PATH=modules), capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_process_actions_widgets():
    node, browser, modules = runtime_tools()
    output = Path(tempfile.mkdtemp(prefix="aps-process-actions-widgets-"))
    result = subprocess.run([node, str(HERE / "process_actions_widgets_probe.cjs"), str(output)],
                            env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
                            capture_output=True, text=True, timeout=240)
    assert result.returncode == 0, result.stdout + result.stderr + "\n" + str(output)
    report = json.loads((output / "process-actions-result.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.")
    assert report["scope"] == "isolated-process-actions-mock"
    assert not report["global_build"] and not report["production_persistence_tested"]
    assert not report["errors"] and not report["external"]
    assert len(report["cases"]) == 40 and all(case["passed"] for case in report["cases"])
    assert len(report["screenshots"]) == 16
    print("PROCESS_ACTIONS_WIDGETS_ARTIFACTS " + str(output), flush=True)
