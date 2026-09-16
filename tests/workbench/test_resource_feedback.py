"""Action-correct feedback labels in the compiled component, without browser or DB."""

import json
import shutil
import subprocess
from pathlib import Path


def test_feedback_uses_explicit_actions_for_delete_save_unlink_and_recovery():
    node = shutil.which("node")
    assert node, "Feedback tests require the build-host Node runtime"
    result = subprocess.run([node, str(Path(__file__).with_name("resource_feedback_probe.cjs"))],
                            check=True, capture_output=True, text=True, timeout=30)
    report = json.loads(result.stdout)
    assert report["checks"] >= 30
    assert report["browser"] is False and report["database"] is False
