"""Theme preference contracts run in a Node VM without an app or browser."""

import json
import os
import shutil
import subprocess
from pathlib import Path


def test_theme_preference_contract_and_failure_visibility():
    node = os.environ.get("WORKBENCH_NODE") or shutil.which("node")
    assert node, "Theme tests require the build-host Node runtime"
    result = subprocess.run(
        [node, str(Path(__file__).with_name("theme_probe.cjs"))],
        check=False, text=True, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, (
        "Theme VM probe failed:\n" + result.stdout + "\n" + result.stderr
    )
    report = json.loads(result.stdout)
    assert report["checks"] == report["passed"] == 23
    assert report["failed"] == 0 and report["failures"] == []
    assert report["network"] == "none" and report["browser"] is False
    assert report["production"] is False
