"""Real pending-state hooks and storage contracts; no DOM, browser or production database."""

import os
import shutil
import subprocess
from pathlib import Path


def test_pending_state_events_preserve_storage_conflicts_and_unknown_results():
    node = os.environ.get("WORKBENCH_NODE") or shutil.which("node")
    assert node, "Set WORKBENCH_NODE to an installed Node runtime"
    result = subprocess.run(
        [node, str(Path(__file__).with_name("pending_state_events_contract.cjs"))],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
