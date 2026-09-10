"""Pure read-policy units; their synthetic adapters are not full-host evidence."""

import subprocess
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_field_and_calibration_read_view_policy_never_retries_live_snapshot_errors(tmp_path):
    node, _, _ = runtime_tools()
    result = subprocess.run([node, str(Path(__file__).with_name("final_execution_read_contract.cjs")), str(tmp_path)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
