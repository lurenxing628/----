from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Sequence

import pytest

from tools import long_gate_fingerprint as fingerprint_mod
from tools.long_gate_fingerprint import LongGateFingerprintError


class _ExitedChrome:
    pid = 12345

    def poll(self) -> int:
        return 7

    def communicate(self, timeout: float = 0) -> tuple:
        del timeout
        return ("chrome stdout detail\n", "chrome stderr sandbox detail\n")

    def wait(self, timeout: float = 0) -> int:
        del timeout
        return 7


class _RunningChrome:
    pid = 12346

    def __init__(self, args: Sequence[str]) -> None:
        profile_dir = ""
        for arg in list(args):
            if str(arg).startswith("--user-data-dir="):
                profile_dir = str(arg).split("=", 1)[1]
        if profile_dir:
            Path(profile_dir).mkdir(parents=True, exist_ok=True)
            Path(profile_dir, "DevToolsActivePort").write_text("9222\n/devtools/browser/test\n", encoding="utf-8")

    def poll(self) -> Any:
        return None

    def communicate(self, timeout: float = 0) -> tuple:
        del timeout
        return ("", "")

    def wait(self, timeout: float = 0) -> int:
        del timeout
        return 0


class _DevToolsResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb

    def read(self, _limit: int) -> bytes:
        return b'{"Browser":"Chrome","webSocketDebuggerUrl":"ws://127.0.0.1/devtools"}'

    def getcode(self) -> int:
        return 200


def _fake_version_run(args, **_kwargs):
    return subprocess.CompletedProcess(args, 0, stdout="Google Chrome 148.0.7778.168\n", stderr="")


def test_chrome_preflight_failure_reports_actionable_diagnostics(tmp_path, monkeypatch):
    chrome = tmp_path / "fake-chrome"
    chrome.write_text("fake chrome\n", encoding="utf-8")
    captured_args = []
    fingerprint_mod._RUNTIME_FINGERPRINT_CACHE.clear()
    monkeypatch.setattr(fingerprint_mod.subprocess, "run", _fake_version_run)
    monkeypatch.setattr(fingerprint_mod.platform, "platform", lambda: "test-platform")

    def fake_popen(args, **_kwargs):
        captured_args.extend(list(args))
        return _ExitedChrome()

    monkeypatch.setattr(fingerprint_mod.subprocess, "Popen", fake_popen)

    with pytest.raises(LongGateFingerprintError) as exc_info:
        fingerprint_mod._chrome_headless_preflight(
            strict=True,
            environment={"APS_CHROME_PATH": str(chrome), "PATH": str(tmp_path), "CI": "true"},
        )

    error = exc_info.value
    details = error.details
    assert "Chrome headless preflight failed" in str(error)
    assert details["runtime_key"] == "chrome_headless_preflight"
    assert details["failure_kind"] == "chrome_exited_before_devtools"
    assert details["chrome_path"] == str(chrome)
    assert details["chrome_realpath"] == str(chrome.resolve())
    assert details["chrome_exists"] is True
    assert details["chrome_version_stdout"] == "Google Chrome 148.0.7778.168"
    assert details["chrome_version_returncode"] == 0
    assert details["stdout_tail"] == "chrome stdout detail\n"
    assert details["stderr_tail"] == "chrome stderr sandbox detail\n"
    assert details["stderr_tail_hash"]
    assert details["profile_dir_created"] is True
    assert details["profile_dir_writable"] is True
    assert details["active_port_exists"] is False
    assert details["waited_ms"] >= 0
    assert details["APS_CHROME_PATH_present"] is True
    assert details["CI"] == "true"
    assert "--headless=new" in details["launch_args_sanitized"]
    assert "--remote-debugging-port=0" in details["launch_args_sanitized"]
    assert "--user-data-dir=<temp-profile>" in details["launch_args_sanitized"]
    assert captured_args[0] == str(chrome)


def test_chrome_preflight_pass_hash_excludes_profile_and_process_details(tmp_path, monkeypatch):
    chrome = tmp_path / "fake-chrome"
    chrome.write_text("fake chrome\n", encoding="utf-8")
    fingerprint_mod._RUNTIME_FINGERPRINT_CACHE.clear()
    monkeypatch.setattr(fingerprint_mod.subprocess, "run", _fake_version_run)
    monkeypatch.setattr(fingerprint_mod.platform, "platform", lambda: "test-platform")
    monkeypatch.setattr(fingerprint_mod.urllib.request, "urlopen", lambda *_args, **_kwargs: _DevToolsResponse())
    monkeypatch.setattr(fingerprint_mod, "_terminate_process_tree", lambda _process: None)
    monkeypatch.setattr(fingerprint_mod.subprocess, "Popen", lambda args, **_kwargs: _RunningChrome(args))

    first = fingerprint_mod._chrome_headless_preflight(
        strict=True,
        environment={"APS_CHROME_PATH": str(chrome), "PATH": str(tmp_path)},
    )
    fingerprint_mod._RUNTIME_FINGERPRINT_CACHE.clear()
    second = fingerprint_mod._chrome_headless_preflight(
        strict=True,
        environment={"APS_CHROME_PATH": str(chrome), "PATH": str(tmp_path)},
    )

    assert first == second
    assert first
