"""Structured failures and uncertain commands, without any real network writes."""

import json
import os
import shutil
import subprocess
from pathlib import Path


def test_resource_transport_reconciles_intent_without_persisting_tokens():
    node = os.environ.get("WORKBENCH_NODE") or shutil.which("node")
    assert node, "Resource transport tests require the build-host Node runtime"
    result = subprocess.run([node, str(Path(__file__).with_name("resource_api_probe.cjs"))],
                            check=True, text=True, capture_output=True, timeout=30)
    report = json.loads(result.stdout)
    assert report["checks"] >= 30
    assert report["network"] == "mock-only" and report["production"] is False
