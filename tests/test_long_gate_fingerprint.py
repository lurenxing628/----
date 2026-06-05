"""单元测试：tools/long_gate_fingerprint 的进程收尾——_terminate_process_tree 先 SIGTERM 等待、超时才升级 SIGKILL；chrome_headless_preflight 成功后走优雅关闭而非硬杀残留 Chrome。"""

from __future__ import annotations

import signal
import subprocess
from pathlib import Path
from typing import Any, Dict, List

import pytest

from tools import long_gate_fingerprint as fingerprint


class _FakeProcess:
    pid = 12345

    def __init__(self, *, wait_timeout: bool = False) -> None:
        self.returncode = None
        self.wait_timeout = wait_timeout
        self.wait_calls: List[float] = []

    def poll(self) -> Any:
        return self.returncode

    def wait(self, timeout: float = 0) -> int:
        self.wait_calls.append(timeout)
        if self.wait_timeout:
            raise subprocess.TimeoutExpired(["fake"], timeout)
        self.returncode = 0
        return 0

    def terminate(self) -> None:
        self.returncode = 0


def test_terminate_process_tree_uses_sigterm_before_sigkill(monkeypatch: pytest.MonkeyPatch) -> None:
    process = _FakeProcess()
    signals: List[Dict[str, Any]] = []

    monkeypatch.setattr(fingerprint.os, "getpgid", lambda pid: 67890)
    monkeypatch.setattr(
        fingerprint.os,
        "killpg",
        lambda pgid, sig: signals.append({"pgid": pgid, "signal": sig}),
    )

    def fail_hard_kill(_process: subprocess.Popen) -> None:
        raise AssertionError("normal termination must not use hard kill")

    monkeypatch.setattr(fingerprint, "_kill_process_tree", fail_hard_kill)

    fingerprint._terminate_process_tree(process)  # type: ignore[arg-type]

    assert signals == [{"pgid": 67890, "signal": signal.SIGTERM}]
    assert process.wait_calls == [5.0]


def test_terminate_process_tree_falls_back_to_hard_kill_after_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    process = _FakeProcess(wait_timeout=True)
    signals: List[Dict[str, Any]] = []
    hard_kills: List[_FakeProcess] = []

    monkeypatch.setattr(fingerprint.os, "getpgid", lambda pid: 67890)
    monkeypatch.setattr(
        fingerprint.os,
        "killpg",
        lambda pgid, sig: signals.append({"pgid": pgid, "signal": sig}),
    )
    monkeypatch.setattr(fingerprint, "_kill_process_tree", lambda proc: hard_kills.append(proc))  # type: ignore[arg-type]

    fingerprint._terminate_process_tree(process)  # type: ignore[arg-type]

    assert signals == [{"pgid": 67890, "signal": signal.SIGTERM}]
    assert hard_kills == [process]


def test_chrome_headless_preflight_uses_graceful_shutdown_after_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fingerprint._RUNTIME_FINGERPRINT_CACHE.clear()
    profile_dir = tmp_path / "chrome-profile"
    profile_dir.mkdir()
    (profile_dir / "DevToolsActivePort").write_text("12345\n/devtools/browser/fake\n", encoding="utf-8")
    process = _FakeProcess()
    terminated: List[_FakeProcess] = []

    class FakeResponse:
        status = 200

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self, _size: int) -> bytes:
            return b'{"Browser":"Fake Chrome","webSocketDebuggerUrl":"ws://127.0.0.1/devtools/browser/fake"}'

        def getcode(self) -> int:
            return 200

    monkeypatch.setattr(
        fingerprint,
        "_chrome_resolution_payload",
        lambda strict=False, environment=None: {
            "status": "found",
            "source": "test",
            "path": "/fake/chrome",
            "realpath": "/fake/chrome",
            "exists": True,
            "reason": "",
        },
    )
    monkeypatch.setattr(fingerprint, "_chrome_executable_identity", lambda strict=False, environment=None: "fake-chrome")
    monkeypatch.setattr(fingerprint, "_chrome_version", lambda strict=False, environment=None: "Fake Chrome 120")
    monkeypatch.setattr(fingerprint.tempfile, "mkdtemp", lambda prefix="": str(profile_dir))
    monkeypatch.setattr(fingerprint.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(fingerprint.urllib.request, "urlopen", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(fingerprint, "_terminate_process_tree", lambda proc: terminated.append(proc))  # type: ignore[arg-type]

    def fail_hard_kill(_process: subprocess.Popen) -> None:
        raise AssertionError("successful preflight should shut Chrome down gracefully")

    monkeypatch.setattr(fingerprint, "_kill_process_tree", fail_hard_kill)

    result = fingerprint._chrome_headless_preflight(strict=True)

    assert result
    assert terminated == [process]
