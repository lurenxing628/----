"""Current shell state is scoped to the exact history entry and original object."""

import json
import os
import shutil
import subprocess
from pathlib import Path


def test_navigation_scope_and_scroll_contract():
    node = os.environ.get("WORKBENCH_NODE") or shutil.which("node")
    assert node, "Navigation contracts require the build-host Node runtime"
    result = subprocess.run(
        [node, str(Path(__file__).with_name("final_foundation_navigation.cjs"))],
        check=False, text=True, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["checks"] == report["passed"] == 28
    assert report["browser"] is False and report["production"] is False
