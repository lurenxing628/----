"""Browser transport failures with deterministic timers and no network calls."""

import json
import os
import shutil
import subprocess
from pathlib import Path


def test_transport_contract_and_bounded_request_lifetime():
    node = os.environ.get("WORKBENCH_NODE") or shutil.which("node")
    assert node, "Transport tests require the build-host Node runtime"
    result = subprocess.run(
        [node, str(Path(__file__).with_name("transport_probe.cjs"))],
        check=True, text=True, capture_output=True, timeout=30,
    )
    report = json.loads(result.stdout)
    assert report["checks"] == 18
    assert report["network"] == "mock-only" and report["production"] is False
