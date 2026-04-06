"""
回归测试：`--runtime-stop` CLI 停机链路。

验证点：
1) 启动真实 `app.py` 后，`python app.py --runtime-stop <repo_root>` 能返回 0。
2) 停机成功后，`<repo_root>/logs` 下的 host/port/db/runtime.json 契约文件会被清理。
3) 无实例场景下再次执行 `--runtime-stop` 仍返回 0，不应报错。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Dict, Tuple


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _contract_paths(log_dir: str) -> Tuple[str, str, str, str]:
    return (
        os.path.join(log_dir, "aps_host.txt"),
        os.path.join(log_dir, "aps_port.txt"),
        os.path.join(log_dir, "aps_db_path.txt"),
        os.path.join(log_dir, "aps_runtime.json"),
    )


def _probe_health(host: str, port: int, timeout: float = 1.5) -> bool:
    url = f"http://{host}:{int(port)}/system/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception:
        return False
    return (
        payload.get("app") == "aps"
        and payload.get("status") == "ok"
        and int(payload.get("contract_version") or 0) == 1
    )


def _assert_repo_not_running(log_dir: str) -> None:
    host_file, port_file, _db_file, _runtime_file = _contract_paths(log_dir)
    if not (os.path.exists(host_file) and os.path.exists(port_file)):
        return
    try:
        host = (Path(host_file).read_text(encoding="utf-8", errors="ignore") or "").strip() or "127.0.0.1"
        port = int((Path(port_file).read_text(encoding="utf-8", errors="ignore") or "").strip())
    except Exception:
        return
    if port > 0 and _probe_health(host, port, timeout=1.0):
        raise RuntimeError("仓库根目录已有运行中的 APS 实例，拒绝执行 --runtime-stop 回归测试")


def _clear_stale_contract(log_dir: str) -> None:
    for path in _contract_paths(log_dir):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except Exception:
            pass


def _wait_for_runtime_contract(log_dir: str, p: subprocess.Popen, timeout_s: float = 20.0) -> Tuple[str, int, str]:
    host_file, port_file, db_file, runtime_file = _contract_paths(log_dir)
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if p.poll() is not None:
            raise RuntimeError(f"应用提前退出（exit_code={p.returncode}），未生成完整运行时契约")
        if all(os.path.exists(path) for path in (host_file, port_file, db_file, runtime_file)):
            try:
                host = (Path(host_file).read_text(encoding="utf-8", errors="ignore") or "").strip() or "127.0.0.1"
                port = int((Path(port_file).read_text(encoding="utf-8", errors="ignore") or "").strip())
                db_path = (Path(db_file).read_text(encoding="utf-8", errors="ignore") or "").strip()
            except Exception:
                time.sleep(0.2)
                continue
            if host and port > 0 and db_path:
                return host, port, db_path
        time.sleep(0.2)
    raise TimeoutError("超时：未生成完整运行时契约")


def _wait_for_process_exit(p: subprocess.Popen, timeout_s: float = 20.0) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if p.poll() is not None:
            return
        time.sleep(0.2)
    raise TimeoutError("超时：`--runtime-stop` 返回后应用进程仍未退出")


def _assert_contract_removed(log_dir: str) -> None:
    remaining = [path for path in _contract_paths(log_dir) if os.path.exists(path)]
    if remaining:
        raise RuntimeError(f"停机后仍残留运行时契约文件：{remaining}")


def main() -> None:
    repo_root = find_repo_root()
    log_dir = os.path.join(repo_root, "logs")
    _assert_repo_not_running(log_dir)
    _clear_stale_contract(log_dir)

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_runtime_stop_")
    env: Dict[str, str] = dict(os.environ)
    env["APS_ENV"] = "production"
    env["APS_HOST"] = "127.0.0.1"
    env["APS_PORT"] = "5788"
    env["APS_DB_PATH"] = os.path.join(tmpdir, "aps.db")
    env["APS_LOG_DIR"] = os.path.join(tmpdir, "logs")
    env["APS_BACKUP_DIR"] = os.path.join(tmpdir, "backups")
    env["APS_EXCEL_TEMPLATE_DIR"] = os.path.join(tmpdir, "templates_excel")
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    p = subprocess.Popen(
        [sys.executable, os.path.join(repo_root, "app.py")],
        cwd=repo_root,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )

    try:
        host, port, _db_path = _wait_for_runtime_contract(log_dir, p, timeout_s=20.0)
        if not _probe_health(host, port, timeout=2.0):
            raise RuntimeError(f"应用启动后健康检查未通过：{host}:{port}")

        stop_proc = subprocess.run(
            [sys.executable, os.path.join(repo_root, "app.py"), "--runtime-stop", repo_root],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if int(stop_proc.returncode or 0) != 0:
            raise RuntimeError(
                "首次 --runtime-stop 应返回 0："
                f"rc={stop_proc.returncode} stdout={stop_proc.stdout!r} stderr={stop_proc.stderr!r}"
            )

        _wait_for_process_exit(p, timeout_s=20.0)
        _assert_contract_removed(log_dir)

        stop_proc_again = subprocess.run(
            [sys.executable, os.path.join(repo_root, "app.py"), "--runtime-stop", repo_root],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if int(stop_proc_again.returncode or 0) != 0:
            raise RuntimeError(
                "无实例场景下的 --runtime-stop 仍应返回 0："
                f"rc={stop_proc_again.returncode} stdout={stop_proc_again.stdout!r} stderr={stop_proc_again.stderr!r}"
            )
        _assert_contract_removed(log_dir)
        print("OK")
    finally:
        try:
            if p.poll() is None:
                p.terminate()
                p.wait(timeout=5)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass


if __name__ == "__main__":
    main()
