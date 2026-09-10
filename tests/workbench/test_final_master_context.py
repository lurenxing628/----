"""Narrow read-context parser regression; real browser restoration is separate."""

import os
import subprocess
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_only_explicit_read_view_fields_can_restore(tmp_path):
    node, _browser, modules = runtime_tools()
    here = Path(__file__).resolve().parent
    result = subprocess.run([node, str(here / "final_master_context_contract.cjs")],
                            env=dict(os.environ, NODE_PATH=modules), capture_output=True, text=True, timeout=90)
    (tmp_path / "context-contract.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"failed":0' in result.stdout


def test_canceled_read_policy_does_not_hide_write_or_network_failure(tmp_path):
    node, _browser, modules = runtime_tools()
    here = Path(__file__).resolve().parent
    result = subprocess.run([node, str(here / "final_master_transport_contract.cjs")],
                            env=dict(os.environ, NODE_PATH=modules), capture_output=True, text=True, timeout=30)
    (tmp_path / "transport-contract.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"cases":16,"failed":0' in result.stdout
