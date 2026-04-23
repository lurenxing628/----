from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, Tuple

_RUNTIME_STATE_FILENAMES = (
    "aps_host.txt",
    "aps_port.txt",
    "aps_db_path.txt",
    "aps_runtime.json",
    "aps_runtime.lock",
    "aps_launch_error.txt",
)


def repo_runtime_state_paths(repo_root: str) -> Iterable[Path]:
    log_dir = Path(repo_root) / "logs"
    for name in _RUNTIME_STATE_FILENAMES:
        yield log_dir / name


def _contract_paths(repo_root: str) -> Tuple[Path, Path, Path, Path, Path, Path]:
    return tuple(repo_runtime_state_paths(repo_root))  # type: ignore[return-value]


def _safe_int(value: object) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    if text.startswith("-"):
        digits = text[1:]
    else:
        digits = text
    if not digits.isdigit():
        return 0
    return int(text)


def _pid_exists(pid: int) -> bool:
    pid_i = _safe_int(pid)
    if pid_i <= 0:
        return False
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid_i}", "/NH", "/FO", "CSV"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
        except Exception:
            return False
        for line in (result.stdout or "").splitlines():
            line_s = str(line or "").strip()
            if line_s.startswith('"') and f',"{pid_i}",' in line_s:
                return True
        return False
    try:
        os.kill(pid_i, 0)
        return True
    except Exception:
        return False


def _probe_health(host: str, port: int, timeout_s: float = 0.75) -> bool:
    host_s = str(host or "").strip() or "127.0.0.1"
    port_i = _safe_int(port)
    if port_i <= 0:
        return False
    try:
        with urllib.request.urlopen(f"http://{host_s}:{port_i}/system/health", timeout=timeout_s) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception:
        return False
    return (
        payload.get("app") == "aps"
        and payload.get("status") == "ok"
        and _safe_int(payload.get("contract_version")) == 1
    )


def _read_runtime_contract(repo_root: str) -> Dict[str, object]:
    _host_file, _port_file, _db_file, runtime_file, _lock_file, _error_file = _contract_paths(repo_root)
    if not runtime_file.exists():
        return {}
    try:
        return dict(json.loads(runtime_file.read_text(encoding="utf-8", errors="ignore") or "{}"))
    except Exception:
        return {}


def _force_kill_pid_tree(pid: int) -> None:
    pid_i = _safe_int(pid)
    if pid_i <= 0:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid_i), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except Exception:
            pass
        return
    try:
        os.kill(pid_i, 9)
    except Exception:
        pass


def _wait_for_process_exit(process: subprocess.Popen, timeout_s: float) -> bool:
    deadline = time.time() + max(float(timeout_s), 0.1)
    while time.time() < deadline:
        if process.poll() is not None:
            return True
        time.sleep(0.2)
    return process.poll() is not None


def _repo_runtime_inactive(repo_root: str, expected_pid: int | None = None) -> bool:
    host_file, port_file, _db_file, runtime_file, lock_file, error_file = _contract_paths(repo_root)
    contract = _read_runtime_contract(repo_root)
    host = str(contract.get("host") or "").strip()
    port = _safe_int(contract.get("port"))
    if not host and host_file.exists():
        host = (host_file.read_text(encoding="utf-8", errors="ignore") or "").strip() or "127.0.0.1"
    if port <= 0 and port_file.exists():
        port = _safe_int(port_file.read_text(encoding="utf-8", errors="ignore"))
    contract_pid = _safe_int(contract.get("pid"))
    tracked_pids = {pid for pid in (expected_pid, contract_pid) if _safe_int(pid) > 0}
    if any(_pid_exists(pid) for pid in tracked_pids):
        return False
    if _probe_health(host, port):
        return False
    return not any(path.exists() for path in (host_file, port_file, runtime_file, lock_file, error_file))


def clear_repo_runtime_state(repo_root: str) -> None:
    for path in repo_runtime_state_paths(repo_root):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            pass


def assert_repo_runtime_stopped(repo_root: str, timeout_s: float = 12.0) -> None:
    deadline = time.time() + max(float(timeout_s), 0.1)
    while time.time() < deadline:
        if _repo_runtime_inactive(repo_root):
            clear_repo_runtime_state(repo_root)
            if _repo_runtime_inactive(repo_root):
                return
        time.sleep(0.2)
    contract = _read_runtime_contract(repo_root)
    raise RuntimeError(f"仓库根目录仍存在运行中的 APS 实例或残留运行态：{contract!r}")


def cleanup_runtime_process(
    repo_root: str,
    entry_script: str,
    process: subprocess.Popen,
    *,
    env: Dict[str, str] | None = None,
) -> None:
    stop_env = dict(os.environ)
    if env:
        stop_env.update({str(key): str(value) for key, value in env.items()})
    stop_env["PYTHONUTF8"] = "1"
    stop_env["PYTHONIOENCODING"] = "utf-8"
    stop_proc: subprocess.Popen | None = None

    try:
        if process.poll() is None:
            stop_proc = subprocess.Popen(
                [sys.executable, os.path.join(repo_root, entry_script), "--runtime-stop", repo_root],
                cwd=repo_root,
                env=stop_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
            try:
                stop_proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                _force_kill_pid_tree(stop_proc.pid)
        if process.poll() is None and not _wait_for_process_exit(process, timeout_s=3.0):
            try:
                process.terminate()
            except Exception:
                pass
            _wait_for_process_exit(process, timeout_s=4.0)
        if process.poll() is None:
            _force_kill_pid_tree(process.pid)
            _wait_for_process_exit(process, timeout_s=4.0)
        deadline = time.time() + 12.0
        while time.time() < deadline:
            if _repo_runtime_inactive(repo_root, expected_pid=process.pid):
                clear_repo_runtime_state(repo_root)
                if _repo_runtime_inactive(repo_root, expected_pid=process.pid):
                    return
            contract_pid = _safe_int(_read_runtime_contract(repo_root).get("pid"))
            if contract_pid > 0 and contract_pid != _safe_int(process.pid):
                _force_kill_pid_tree(contract_pid)
            time.sleep(0.25)
    finally:
        if stop_proc is not None and stop_proc.poll() is None:
            _force_kill_pid_tree(stop_proc.pid)
        if process.poll() is None:
            _force_kill_pid_tree(process.pid)
        clear_repo_runtime_state(repo_root)
