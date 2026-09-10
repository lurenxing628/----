"""Pure report read-view policy tests, separate from the real full-host proof."""

import subprocess
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_report_read_view_policy_does_not_retry_live_snapshot_errors(tmp_path):
    node, _, _ = runtime_tools()
    script = Path(__file__).with_name("final_execution_report_contract.cjs")
    result = subprocess.run([node, str(script), str(tmp_path)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
