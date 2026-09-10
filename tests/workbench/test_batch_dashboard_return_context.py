"""Narrow Batch return envelope and callback contracts; live dashboard is separate."""

import os
import subprocess
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_batch_dashboard_return_envelope_and_button(tmp_path):
    node, _browser, modules = runtime_tools()
    here = Path(__file__).resolve().parent
    result = subprocess.run([node, str(here / "batch_dashboard_return_contract.cjs")],
                            env=dict(os.environ, NODE_PATH=modules), capture_output=True, text=True, timeout=90)
    (tmp_path / "batch-dashboard-return-contract.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"failed":0' in result.stdout
