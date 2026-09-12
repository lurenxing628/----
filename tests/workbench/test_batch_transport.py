"""Batch validation preserves payloads; adapter keeps the exact pending namespace."""

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


def test_batch_validation_preserves_payload_and_unknown_fields():
    node, _browser, modules = runtime_tools()
    probe = Path(__file__).with_name("batch_ui_contract.cjs")
    result = subprocess.run([node, str(probe)], capture_output=True, text=True,
                            env=dict(os.environ, NODE_PATH=modules), timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
