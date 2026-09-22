"""Dialog focus restoration and tooltip-reason Button contracts run in a Node VM without a browser."""

import json
import os
import shutil
import subprocess
from pathlib import Path


def test_modal_focus_restore_and_tooltip_reason_contract():
    node = os.environ.get("WORKBENCH_NODE") or shutil.which("node")
    assert node, "Shared control contracts require the build-host Node runtime"
    result = subprocess.run(
        [node, str(Path(__file__).with_name("modal_focus_restore_contract.cjs"))],
        check=False, text=True, capture_output=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["checks"] == report["passed"] == 9
    assert report["browser"] is False and report["production"] is False
