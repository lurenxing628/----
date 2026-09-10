"""Supplementary source-level context validation, separate from real browsers."""

import json
import os
import subprocess

from tests.workbench.final_operations_support import REPO
from tests.workbench.test_live_browser import runtime_tools


def test_final_operations_persistent_context_and_navigation_boundaries(tmp_path):
    node, _browser, modules = runtime_tools()
    result = subprocess.run([node, str(REPO / "tests/workbench/final_operations_context_contract.cjs")],
        cwd=str(REPO), capture_output=True, text=True, env=dict(os.environ, NODE_PATH=modules), timeout=40)
    (tmp_path / "context-contract.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["passed"] and payload["dashboard_negative"] == 7 and payload["system_negative"] == 2
