"""Regression for the actual Win7 PowerShell stdout which omitted Chrome's root PID."""
from __future__ import annotations

import hashlib

import pytest

from web.bootstrap.launcher_chrome import _parse_chrome_pid_output, _stop_aps_chrome_with_result

# Win7 Installed --app capture, 2026-09-26 17:19:22. This is the complete
# 38-byte stdout.bin saved with the original acceptance evidence, not a new run.
WIN7_STDOUT = b"\xef\xbb\xbf3124\r\n596\r\n3812\r\n3444\r\n3004\r\n1712\r\n"


def test_real_win7_stdout_keeps_main_chrome_pid():
    assert hashlib.sha256(WIN7_STDOUT).hexdigest() == "0aca1bc48c1e9470a326d27d8d4d907de681064cfc83c696339a6965ee3a766f"
    assert _parse_chrome_pid_output(WIN7_STDOUT.decode("utf-8")) == [3124, 596, 3812, 3444, 3004, 1712]


@pytest.mark.parametrize("output, expected", [
    ("\ufeff1340\r\n1592", [1340, 1592]),
    ("\ufeffProcessId=1340\r\n1592", [1340, 1592]),
    ("1340\r\n\ufeff1592", [1340]),
    ("\ufeff\ufeff1340\r\n1592", [1592]),
    ("1340\n1340\n0\n-1\nnoise\n²\n１２", [1340]),
])
def test_only_one_stream_leading_bom_is_metadata(output, expected):
    assert _parse_chrome_pid_output(output) == expected


def test_stop_receives_main_pid_before_children_from_real_win7_output():
    killed = []
    snapshots = iter([_parse_chrome_pid_output(WIN7_STDOUT.decode("utf-8")), []])
    result = _stop_aps_chrome_with_result(
        r"C:\APS\user-data\chrome109_profile",
        list_pids=lambda _profile: next(snapshots),
        kill_pid=lambda pid: killed.append(pid) or True,
    )
    assert result.ok
    assert killed == [3124, 596, 3812, 3444, 3004, 1712]
