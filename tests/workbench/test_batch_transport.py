"""Batch adapter invokes the shared transport and exact pending namespace."""

import os
import subprocess
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_batch_shared_transport_namespace():
    node, _browser, modules = runtime_tools()
    probe = Path(__file__).with_name("batch_api_probe.cjs")
    result = subprocess.run([node, str(probe)], capture_output=True, text=True,
                            env=dict(os.environ, NODE_PATH=modules), timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
