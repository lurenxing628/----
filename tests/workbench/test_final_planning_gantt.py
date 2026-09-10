"""Focused client-model regressions; not a substitute for full-entry K/B/P."""

import json
import os
import subprocess
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_changed_only_uses_captured_change_and_keeps_full_axis():
    node, _, modules = runtime_tools()
    result = subprocess.run([node, str(Path(__file__).with_name("final_planning_gantt_model.cjs"))],
                            env=dict(os.environ, NODE_PATH=modules), capture_output=True,
                            text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {"model_only": True, "real_full_entry_evidence": False, "checks": 8}
