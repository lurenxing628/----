"""Browser-independent three-way route drafts and lossless serialization."""

import shutil
import subprocess
from pathlib import Path


def test_route_draft_merge_and_serialization():
    node = shutil.which("node")
    assert node, "Contract tests require the build-host Node runtime"
    probe = Path(__file__).with_name("process_route_draft_probe.cjs")
    result = subprocess.run([node, str(probe)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
