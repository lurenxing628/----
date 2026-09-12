"""Receipt output normalization preserves matches without quadratic numeric scans."""

import itertools
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tools.quality_gate_shared import _normalize_command_output_for_policy


@pytest.mark.parametrize(
    "value, expected",
    [
        ("collected in 1.25 seconds", "collected in <seconds> seconds\n"),
        ("1.2.3 seconds", "1.<seconds> seconds\n"),
        ("1..23 seconds", "1..<seconds> seconds\n"),
        ("abc123 seconds", "abc<seconds> seconds\n"),
        ("-1.25 seconds", "-<seconds> seconds\n"),
        ("1e3 seconds", "1e<seconds> seconds\n"),
        ("123. seconds", "123. seconds\n"),
        ("123 second", "123 second\n"),
        ("12 34 seconds", "12 <seconds> seconds\n"),
        ("１２3 seconds", "１２<seconds> seconds\n"),
        ("١2 seconds", "١<seconds> seconds\n"),
        ("123\n4 seconds", "123\n<seconds> seconds\n"),
        ("done in 0.12s\r\n4 seconds\r\n", "done in <seconds>s\n<seconds> seconds\n"),
    ],
)
def test_receipt_duration_normalization_preserves_existing_examples(value, expected):
    assert _normalize_command_output_for_policy(value, policy="normalized") == expected
    assert _normalize_command_output_for_policy(value, policy="exact") == value


def test_duration_normalization_matches_legacy_on_small_digit_and_decimal_inputs():
    legacy = re.compile(r"[0-9]+(?:\.[0-9]+)? seconds")
    for length in range(6):
        for prefix in itertools.product("12.e- ", repeat=length):
            value = "".join(prefix) + " seconds"
            expected = legacy.sub("<seconds> seconds", value).strip() + "\n"
            assert _normalize_command_output_for_policy(value, policy="normalized") == expected, value


def test_collect_receipt_with_262143_digit_nodeid_finishes_in_bounded_subprocess():
    # Keep the giant input inside the child; parametrizing it would grow pytest's own IDs.
    source = r'''
import hashlib
import json
import time
from tools.quality_gate_shared import build_quality_gate_command_receipt

nodeid = "tests/example.py::test_input[" + "9" * 262143 + "]\n"
stdout = nodeid + "17073 tests collected in 0.12s\n"
expected = nodeid + "17073 tests collected in <seconds>s\n"
command = {"display": "python -m pytest --collect-only -q tests",
           "args": ["python", "-m", "pytest", "--collect-only", "-q", "tests"],
           "capture_output": True, "output_policy": "normalized"}
started = time.perf_counter()
receipt = build_quality_gate_command_receipt(command, run_id="long-nodeid-regression",
    command_index=7, returncode=0, stdout=stdout, stderr="")
assert receipt["stdout_sha256"] == hashlib.sha256(expected.encode("utf-8")).hexdigest()
assert receipt["stderr_sha256"] == hashlib.sha256(b"").hexdigest()
assert receipt["returncode"] == 0 and receipt["output_policy"] == "normalized"
print(json.dumps({"elapsed_s": time.perf_counter() - started, "digits": 262143}))
'''
    result = subprocess.run(
        [sys.executable, "-B", "-c", source],
        cwd=str(Path(__file__).resolve().parents[2]),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["digits"] == 262143
