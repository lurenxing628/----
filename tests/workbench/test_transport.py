"""Browser transport failures with deterministic timers and no network calls."""

import json
import subprocess
from pathlib import Path

from tests.workbench.node_runtime_support import node_runtime


def test_transport_contract_and_bounded_request_lifetime():
    result = subprocess.run(
        [node_runtime(), str(Path(__file__).with_name("transport_probe.cjs"))],
        check=True, text=True, capture_output=True, timeout=30,
    )
    report = json.loads(result.stdout)
    assert report["checks"] == 18
    assert report["network"] == "mock-only" and report["production"] is False
