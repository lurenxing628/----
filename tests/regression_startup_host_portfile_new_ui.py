"""
回归测试：app_new_ui 启动入口 host/port 文件契约

验证点：
1) APS_HOST 设为 hostname/IPv6/非法值时，不应导致 app_new_ui.py 启动崩溃（应回退到 127.0.0.1）。
2) 端口文件契约：无论 APS_LOG_DIR 指向哪里，都应写入 <repo_root>/logs/aps_port.txt（仅数字+换行）。
3) Host 文件契约：无论 APS_LOG_DIR 指向哪里，都应写入 <repo_root>/logs/aps_host.txt（一行 host + 换行）。
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict


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


def _wait_port_open(host: str, port: int, p: subprocess.Popen, timeout_s: float = 12.0) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if p.poll() is not None:
            raise RuntimeError(f"进程提前退出（exit_code={p.returncode}），端口未就绪：{host}:{port}")
        if _is_port_open(host, port):
            return
        time.sleep(0.2)
    raise TimeoutError(f"超时：端口未就绪：{host}:{port}")


def _run_case(repo_root: str, aps_host: str) -> None:
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
    try:
        os.remove(port_file)
    except Exception:
        pass
    try:
        os.remove(host_file)
    except Exception:
        pass

    p = subprocess.Popen(
        [sys.executable, os.path.join(repo_root, "app_new_ui.py")],
        cwd=repo_root,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    try:
        port = _wait_for_port_file(port_file, p, timeout_s=15.0)
        if port <= 0:
            raise RuntimeError(f"端口文件内容非法：{port_file} -> {port}")
        host = _wait_for_host_file(host_file, p, timeout_s=15.0)
        if host != "127.0.0.1":
            raise RuntimeError(f"host 文件内容不符合预期：{host_file} -> {host!r}（期望 '127.0.0.1'）")
        _wait_port_open(host, port, p, timeout_s=15.0)
    finally:
        try:
            p.terminate()
            p.wait(timeout=6)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass


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
