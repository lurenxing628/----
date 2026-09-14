"""Stop must not confuse shutdown acknowledgement or HTTP loss with process exit."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from tests.app_runtime.runtime_stop_draining_support import (
    REPO_ROOT,
    isolated_env,
    pending_http_write,
    running_runtime,
    subprocess_command,
    wait_for_file,
)
from web.bootstrap import launcher_stop


def _artifact_bytes(root: Path):
    paths = list((root / "logs").glob("aps_*")) + [root / "work.sqlite.lock"]
    return {path: path.read_bytes() for path in paths if path.is_file()}


def _rows(root: Path):
    with sqlite3.connect(str(root / "work.sqlite")) as conn:
        return conn.execute("SELECT id, value FROM work").fetchall()


def _guard_owned_process(monkeypatch, process):
    # The Windows exe query is unavailable on POSIX. Confirm only the Popen child
    # whose argv and live handle this fixture owns; PID and HTTP probes stay real.
    def matches(pid, exe_path):
        assert pid == process.pid
        assert os.path.realpath(exe_path) == os.path.realpath(sys.executable)
        return process.poll() is None

    def refuse_kill(pid):
        pytest.fail(f"Stop attempted to kill the owned draining PID {pid}")

    monkeypatch.setattr(launcher_stop, "_pid_matches_contract", matches)
    monkeypatch.setattr(launcher_stop, "_kill_runtime_pid", refuse_kill)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")


@pytest.mark.parametrize("mode", ["accepted", "healthy", "unresponsive", "rejected"])
def test_stop_timeout_preserves_draining_pid_locks_and_write(tmp_path, monkeypatch, capsys, mode):
    chrome_calls = []
    with running_runtime(tmp_path, mode) as process, pending_http_write(tmp_path, process) as response:
        _guard_owned_process(monkeypatch, process)

        def stop_chrome(profile_dir):
            assert process.poll() == 0, "Chrome cleanup ran before runtime exit"
            chrome_calls.append(profile_dir)
            return launcher_stop._StopChromeResult(True, "stopped", profile_dir, [], [], [])

        monkeypatch.setattr(launcher_stop, "_stop_aps_chrome_with_result", stop_chrome)
        before = _artifact_bytes(tmp_path)
        assert len(before) == 6
        started = time.monotonic()
        rc = launcher_stop.stop_runtime_from_dir(str(tmp_path / "logs"), timeout_s=0.1, stop_aps_chrome=True)
        elapsed = time.monotonic() - started

        assert rc == 1
        assert 1.5 <= elapsed < 6.0, "Stop must finish its bounded wait without a kill grace period"
        assert process.poll() is None
        assert before == _artifact_bytes(tmp_path)
        assert _rows(tmp_path) == []
        assert response == []
        assert chrome_calls == []
        assert (tmp_path / "shutdown-seen").exists()
        assert (tmp_path / "accepted").exists() is (mode != "rejected")
        stderr = capsys.readouterr().err
        assert "runtime_stop_failed" in stderr
        assert "尚未确认退出" in stderr
        assert "稍后重试" in stderr
        assert "shutdown_requested={}".format(mode in {"accepted", "healthy"}) in stderr

        (tmp_path / "release").touch()
        assert process.wait(timeout=10) == 0
        assert _rows(tmp_path) == [(1, "committed after drain")]
        assert not (tmp_path / "work.sqlite.lock").exists()
        assert not (tmp_path / "logs" / "aps_runtime.lock").exists()
        assert launcher_stop.stop_runtime_from_dir(str(tmp_path / "logs"), stop_aps_chrome=True) == 0
        assert chrome_calls == [str(tmp_path / "chrome-profile")]
        assert not (tmp_path / "logs" / "aps_runtime.json").exists()
    assert response == [200]


def test_stop_succeeds_only_after_pending_write_commits_and_pid_exits(tmp_path, monkeypatch):
    with running_runtime(tmp_path) as process, pending_http_write(tmp_path, process):
        _guard_owned_process(monkeypatch, process)

        def release_after_acceptance():
            wait_for_file(tmp_path / "accepted", process)
            time.sleep(0.5)
            (tmp_path / "release").touch()

        release_thread = threading.Thread(target=release_after_acceptance)
        release_thread.start()
        try:
            assert launcher_stop.stop_runtime_from_dir(str(tmp_path / "logs"), timeout_s=5.0) == 0
            assert process.poll() == 0
            assert _rows(tmp_path) == [(1, "committed after drain")]
            assert not (tmp_path / "work.sqlite.lock").exists()
        finally:
            (tmp_path / "release").touch()
            release_thread.join(timeout=10)
            assert not release_thread.is_alive()


def test_real_stop_cli_reports_not_exited_after_token_acceptance(tmp_path):
    with running_runtime(tmp_path) as process, pending_http_write(tmp_path, process):
        before = _artifact_bytes(tmp_path)
        started = time.monotonic()
        result = subprocess.run(
            subprocess_command("stop", tmp_path), cwd=str(REPO_ROOT), env=isolated_env(tmp_path),
            capture_output=True, text=True, encoding="utf-8", timeout=20,
        )
        elapsed = time.monotonic() - started
        assert result.returncode == 1, result.stderr
        assert 10.0 <= elapsed < 18.0
        assert "尚未确认退出" in result.stderr
        assert "shutdown_requested=True" in result.stderr
        assert (tmp_path / "accepted").exists()
        assert process.poll() is None
        assert before == _artifact_bytes(tmp_path)
        contract = json.loads((tmp_path / "logs" / "aps_runtime.json").read_text(encoding="utf-8"))
        assert contract["pid"] == process.pid
        expected_db_path = os.path.normcase(os.path.abspath(str(tmp_path / "work.sqlite")))
        assert contract["db_path"] == expected_db_path
        assert _rows(tmp_path) == []
