"""Real Windows process lifetime and Unicode identity, plus failure-side guards."""
from __future__ import annotations

import os
import subprocess
import sys
import time

import pytest

from web.bootstrap import launcher_processes as processes
from web.bootstrap import launcher_win32 as native


@pytest.mark.skipif(os.name != "nt", reason="real Windows handles required")
def test_live_and_exited_process_are_distinct_without_external_probes(monkeypatch):
    child = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"], stdin=subprocess.PIPE)
    try:
        def forbidden(*args, **kwargs):
            pytest.fail("A process probe must not launch tasklist or PowerShell")
        monkeypatch.setattr(processes.subprocess, "run", forbidden)
        start = time.monotonic()
        for _ in range(25):
            assert processes._pid_state(child.pid) is True
            assert processes._pid_matches_contract(child.pid, sys.executable) is True
            assert processes._pid_matches_contract(child.pid, sys.executable + ".other") is False
        assert time.monotonic() - start < 2
        child.communicate(timeout=5)
        assert processes._pid_state(child.pid) is False
        assert processes._query_process_executable_path(child.pid) == ""
    finally:
        if child.poll() is None:
            child.communicate(timeout=5)


def test_native_access_denied_stays_unknown_without_slow_fallback(monkeypatch, capsys):
    from types import SimpleNamespace
    monkeypatch.setattr(processes, "os", SimpleNamespace(name="nt", path=os.path))
    monkeypatch.setattr(native, "available", lambda: True)
    def denied(pid):
        raise PermissionError("access denied")
    monkeypatch.setattr(native, "pid_exists", denied)
    monkeypatch.setattr(native, "executable_path", denied)
    monkeypatch.setattr(processes.subprocess, "run", lambda *a, **k: pytest.fail("unexpected fallback"))
    assert processes._pid_state(1234) is None
    assert processes._pid_matches_contract(1234, sys.executable) is None
    assert "access denied" in capsys.readouterr().err


def test_native_unicode_path_keeps_identity(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(processes, "os", SimpleNamespace(name="nt", path=os.path))
    monkeypatch.setattr(native, "available", lambda: True)
    path = r"C:\验收 目录\排产系统.exe"
    monkeypatch.setattr(native, "executable_path", lambda pid: path)
    assert processes._pid_matches_contract(1234, path) is True
    assert processes._pid_matches_contract(1234, r"C:\验收 目录\另一个.exe") is False
