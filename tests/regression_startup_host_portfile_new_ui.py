"""
回归测试：app_new_ui 启动入口 host/port 文件契约

验证点：
1) APS_HOST 设为 hostname/IPv6/非法值时，不应导致 app_new_ui.py 启动崩溃（应回退到 127.0.0.1）。
2) 端口文件契约：无论 APS_LOG_DIR 指向哪里，都应写入 <repo_root>/logs/aps_port.txt（仅数字+换行）。
3) Host 文件契约：无论 APS_LOG_DIR 指向哪里，都应写入 <repo_root>/logs/aps_host.txt（一行 host + 换行）。
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Dict

from tests.runtime_cleanup_helper import assert_repo_runtime_stopped, cleanup_runtime_process, clear_repo_runtime_state


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _is_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=0.4):
            return True
    except Exception:
        return False


def _read_port_file(path: str) -> int:
    txt = Path(path).read_text(encoding="utf-8", errors="ignore").strip()
    return int(txt)


def _read_host_file(path: str) -> str:
    txt = Path(path).read_text(encoding="utf-8", errors="ignore").strip()
    return str(txt)


def _read_db_file(path: str) -> str:
    txt = Path(path).read_text(encoding="utf-8", errors="ignore").strip()
    return str(txt)


def _read_runtime_contract(path: str) -> dict:
    txt = Path(path).read_text(encoding="utf-8", errors="ignore").strip()
    return dict(json.loads(txt))


def _normalize_path(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def _wait_for_port_file(path: str, p: subprocess.Popen, timeout_s: float = 12.0) -> int:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if p.poll() is not None:
            raise RuntimeError(f"进程提前退出（exit_code={p.returncode}），未生成端口文件：{path}")
        if os.path.exists(path):
            try:
                return _read_port_file(path)
            except Exception:
                pass
        time.sleep(0.2)
    raise TimeoutError(f"超时：未生成端口文件：{path}")


def _wait_for_host_file(path: str, p: subprocess.Popen, timeout_s: float = 12.0) -> str:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if p.poll() is not None:
            raise RuntimeError(f"进程提前退出（exit_code={p.returncode}），未生成 host 文件：{path}")
        if os.path.exists(path):
            try:
                host = _read_host_file(path)
                if host:
                    return host
            except Exception:
                pass
        time.sleep(0.2)
    raise TimeoutError(f"超时：未生成 host 文件：{path}")


def _wait_for_db_file(path: str, p: subprocess.Popen, timeout_s: float = 12.0) -> str:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if p.poll() is not None:
            raise RuntimeError(f"进程提前退出（exit_code={p.returncode}），未生成 db_path 文件：{path}")
        if os.path.exists(path):
            try:
                db_path = _read_db_file(path)
                if db_path:
                    return db_path
            except Exception:
                pass
        time.sleep(0.2)
    raise TimeoutError(f"超时：未生成 db_path 文件：{path}")


def _wait_for_runtime_contract(
    path: str,
    p: subprocess.Popen,
    *,
    expected_pid: int,
    expected_ui_mode: str,
    timeout_s: float = 12.0,
) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if p.poll() is not None:
            raise RuntimeError(f"进程提前退出（exit_code={p.returncode}），未生成运行时契约：{path}")
        if os.path.exists(path):
            try:
                payload = _read_runtime_contract(path)
            except Exception:
                time.sleep(0.2)
                continue
            try:
                pid = int(payload.get("pid") or 0)
                port = int(payload.get("port") or 0)
            except Exception:
                pid = 0
                port = 0
            if (
                pid == int(expected_pid)
                and port > 0
                and str(payload.get("host") or "").strip()
                and str(payload.get("db_path") or "").strip()
                and str(payload.get("ui_mode") or "").strip() == expected_ui_mode
            ):
                return payload
        time.sleep(0.2)
    raise TimeoutError(f"超时：未等到当前子进程写入运行时契约：{path}")


def _wait_port_open(host: str, port: int, p: subprocess.Popen, timeout_s: float = 12.0) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if p.poll() is not None:
            raise RuntimeError(f"进程提前退出（exit_code={p.returncode}），端口未就绪：{host}:{port}")
        if _is_port_open(host, port):
            return
        time.sleep(0.2)
    raise TimeoutError(f"超时：端口未就绪：{host}:{port}")


def _assert_health(host: str, port: int, p: subprocess.Popen, timeout_s: float = 12.0) -> None:
    url = f"http://{host}:{port}/system/health"
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if p.poll() is not None:
            raise RuntimeError(f"进程提前退出（exit_code={p.returncode}），健康检查未就绪：{url}")
        try:
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
            if (
                payload.get("app") == "aps"
                and payload.get("status") == "ok"
                and int(payload.get("contract_version") or 0) == 1
                and str(payload.get("ui_mode") or "") == "new_ui"
            ):
                return
        except Exception:
            pass
        time.sleep(0.2)
    raise TimeoutError(f"超时：健康检查未就绪：{url}")


def _run_case(repo_root: str, aps_host: str) -> None:
    from web.bootstrap.launcher import default_chrome_profile_dir

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_startup_new_ui_")
    test_db = os.path.join(tmpdir, "aps.db")
    test_logs = os.path.join(tmpdir, "logs")
    test_backups = os.path.join(tmpdir, "backups")
    test_templates = os.path.join(tmpdir, "templates_excel")
    os.makedirs(test_logs, exist_ok=True)
    os.makedirs(test_backups, exist_ok=True)
    os.makedirs(test_templates, exist_ok=True)

    env: Dict[str, str] = dict(os.environ)
    env["APS_ENV"] = "production"
    env["APS_HOST"] = aps_host
    env["APS_DB_PATH"] = test_db
    env["APS_LOG_DIR"] = test_logs
    env["APS_BACKUP_DIR"] = test_backups
    env["APS_EXCEL_TEMPLATE_DIR"] = test_templates
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    port_file = os.path.join(repo_root, "logs", "aps_port.txt")
    host_file = os.path.join(repo_root, "logs", "aps_host.txt")
    db_file = os.path.join(repo_root, "logs", "aps_db_path.txt")
    runtime_file = os.path.join(repo_root, "logs", "aps_runtime.json")
    clear_repo_runtime_state(repo_root)
    assert_repo_runtime_stopped(repo_root)

    p = subprocess.Popen(
        [sys.executable, os.path.join(repo_root, "app_new_ui.py")],
        cwd=repo_root,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    try:
        contract = _wait_for_runtime_contract(
            runtime_file,
            p,
            expected_pid=p.pid,
            expected_ui_mode="new_ui",
            timeout_s=15.0,
        )
        port = _wait_for_port_file(port_file, p, timeout_s=15.0)
        if port <= 0:
            raise RuntimeError(f"端口文件内容非法：{port_file} -> {port}")
        if int(contract.get("port") or 0) != port:
            raise RuntimeError(f"runtime contract port 与镜像文件不一致：{contract!r} / {port_file} -> {port}")
        host = _wait_for_host_file(host_file, p, timeout_s=15.0)
        if host != "127.0.0.1":
            raise RuntimeError(f"host 文件内容不符合预期：{host_file} -> {host!r}（期望 '127.0.0.1'）")
        if str(contract.get("host") or "").strip() != host:
            raise RuntimeError(f"runtime contract host 与镜像文件不一致：{contract!r} / {host_file} -> {host!r}")
        _wait_port_open(host, port, p, timeout_s=15.0)
        _assert_health(host, port, p, timeout_s=15.0)
        runtime_db = _wait_for_db_file(db_file, p, timeout_s=15.0)
        expected_db = _normalize_path(test_db)
        if runtime_db != expected_db:
            raise RuntimeError(f"db_path 文件内容不符合预期：{db_file} -> {runtime_db!r}（期望 {expected_db!r}）")
        if _normalize_path(str(contract.get("db_path") or "")) != expected_db:
            raise RuntimeError(f"runtime contract db_path 不符合预期：{runtime_file} -> {contract!r}")
        if int(contract.get("contract_version") or 0) != 1:
            raise RuntimeError(f"runtime contract version 异常：{contract!r}")
        if _normalize_path(str(contract.get("runtime_dir") or "")) != _normalize_path(repo_root):
            raise RuntimeError(f"runtime contract runtime_dir 异常：{contract!r}")
        if _normalize_path(str((contract.get("data_dirs") or {}).get("log_dir") or "")) != _normalize_path(test_logs):
            raise RuntimeError(f"runtime contract data_dirs.log_dir 异常：{contract!r}")
        if _normalize_path(str(contract.get("exe_path") or "")) != _normalize_path(sys.executable):
            raise RuntimeError(f"runtime contract exe_path 异常：{contract!r}")
        if not str(contract.get("owner") or "").strip():
            raise RuntimeError(f"runtime contract owner 不应为空：{contract!r}")
        if str(contract.get("shutdown_path") or "") != "/system/runtime/shutdown":
            raise RuntimeError(f"runtime contract shutdown_path 异常：{contract!r}")
        if not str(contract.get("shutdown_token") or "").strip():
            raise RuntimeError(f"runtime contract shutdown_token 不应为空：{contract!r}")
        expected_profile = _normalize_path(default_chrome_profile_dir(repo_root))
        if _normalize_path(str(contract.get("chrome_profile_dir") or "")) != expected_profile:
            raise RuntimeError(f"runtime contract chrome_profile_dir 异常：{contract!r}")
    finally:
        cleanup_runtime_process(repo_root, "app_new_ui.py", p, env=env)


def main() -> None:
    repo_root = find_repo_root()
    cases = [
        "localhost",
        "::1",
        "not_a_host",
        "192.0.2.123",
    ]
    for h in cases:
        _run_case(repo_root, h)

    print("OK")


if __name__ == "__main__":
    main()
