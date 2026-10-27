"""The single browser transport: envelopes, unified errors, verdicts and downloads with mocked fetch only."""

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
    assert report["network"] == "mock-only" and report["production"] is False
    assert report["checks"] == len(report["cases"]) == 94
    cases = set(report["cases"])
    # Q2-A: one definite-rejection verdict for every command module.
    for status in (400, 404, 409, 422, 503):
        assert f"rejected for committed:false HTTP {status}" in cases
    for status in (403, 413, 500):
        assert f"not rejected for committed:false HTTP {status}" in cases
    assert "request_key_conflict is never a rejection" in cases
    assert "failure maps the backend failure envelope to the unified error" in cases
    assert "envelope rejects sixth meta key" in cases and "envelope accepts a null snapshot_ref" in cases
    assert "lookup turns 404 receipt_not_found into null" in cases
    assert "types maps the four download formats to frozen MIME types" in cases
    assert "rejected for a local failure that never reached the server" in cases
    assert "read network failure is a definite non-commit, lookup failure never is" in cases
    assert "download rejects a missing filename" in cases
    assert "download rejects a suffix that does not match the type: CSV saved as .xlsx" in cases
