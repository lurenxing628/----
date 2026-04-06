"""
打包后 exe 冷启动验收脚本（用于 Win7/离线交付验收）。

用法：
  python validate_dist_exe.py "dist\\排产系统\\排产系统.exe"

验证点（最小闭环）：
  - 进程可启动
  - 运行时 host/port 文件可生成并可解析
  - 健康检查接口可访问（GET /system/health）
  - 可访问关键页面（/personnel/ /equipment/ /process/ /scheduler/ /system/backup）

注意：
  - 该脚本会启动 exe 并在验证后结束进程
  - 实际访问地址以 logs/aps_host.txt 与 logs/aps_port.txt 为准
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_EXPECTED_CONTRACT_VERSION = 1


def _is_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=0.5):
            return True
    except Exception:
        return False


def _http_get(url: str, timeout: float = 2.5) -> int:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(getattr(resp, "status", 200))
    except urllib.error.HTTPError as e:
        return int(getattr(e, "code", 500))


def _http_get_text(url: str, timeout: float = 2.5) -> str:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _normalize_db_path(path: str) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    return os.path.normcase(os.path.abspath(raw))


def _runtime_contract_paths(log_dir: str) -> tuple[str, str, str]:
    return (
        os.path.join(log_dir, "aps_host.txt"),
        os.path.join(log_dir, "aps_port.txt"),
        os.path.join(log_dir, "aps_db_path.txt"),
    )


def _read_port_file(path: str) -> int:
    return int(Path(path).read_text(encoding="utf-8", errors="ignore").strip())


def _read_host_file(path: str) -> str:
    return str(Path(path).read_text(encoding="utf-8", errors="ignore").strip())


def _read_db_file(path: str) -> str:
    return _normalize_db_path(Path(path).read_text(encoding="utf-8", errors="ignore").strip())


def _read_runtime_contract(log_dir: str) -> tuple[str, int, str] | None:
    host_file, port_file, db_file = _runtime_contract_paths(log_dir)
    if not (os.path.exists(host_file) and os.path.exists(port_file) and os.path.exists(db_file)):
        return None

    host = _read_host_file(host_file)
    if not host:
        raise RuntimeError(f"运行时契约文件解析失败：host 文件为空：{host_file}")

    try:
        port = _read_port_file(port_file)
    except Exception as e:
        raise RuntimeError(f"运行时契约文件解析失败：port 文件无效：{port_file}") from e
    if port <= 0:
        raise RuntimeError(f"运行时契约文件解析失败：port 必须大于 0：{port_file}")

    db_path = _read_db_file(db_file)
    if not db_path:
        raise RuntimeError(f"运行时契约文件解析失败：db_path 文件为空：{db_file}")

    return host, port, db_path


def _clear_runtime_contract_files(log_dir: str) -> None:
    paths = _runtime_contract_paths(log_dir)
    for path in paths:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except Exception:
            pass
    remaining = [path for path in paths if os.path.exists(path)]
    if remaining:
        raise RuntimeError(f"无法清理旧的运行时契约文件：{remaining}")


def _assert_process_running(p: subprocess.Popen, context: str) -> None:
    exit_code = p.poll()
    if exit_code is not None:
        raise RuntimeError(f"进程提前退出（exit_code={exit_code}），{context}")


def _wait_for_runtime_contract(log_dir: str, p: subprocess.Popen, timeout_s: float = 20.0) -> tuple[str, int, str]:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        _assert_process_running(p, "未生成运行时 host/port/db 契约文件。")
        contract = _read_runtime_contract(log_dir)
        if contract is not None:
            return contract
        time.sleep(0.2)
    raise TimeoutError("超时：未生成运行时 host/port/db 契约文件。")


def _wait_port_open(host: str, port: int, p: subprocess.Popen, timeout_s: float = 20.0) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        _assert_process_running(p, f"端口未就绪：{host}:{port}")
        if _is_port_open(host, port):
            return
        time.sleep(0.2)
    raise TimeoutError(f"超时：端口未就绪：{host}:{port}")


def _assert_health(base_url: str, timeout: float = 3.0) -> dict:
    text = _http_get_text(base_url + "/system/health", timeout=timeout)
    payload = json.loads(text)
    if payload.get("app") != "aps":
        raise RuntimeError(f"健康检查返回的 app 标识不正确：{payload!r}")
    if payload.get("status") != "ok":
        raise RuntimeError(f"健康检查状态不正确：{payload!r}")
    try:
        contract_version = int(payload.get("contract_version") or 0)
    except Exception:
        contract_version = 0
    if contract_version != _EXPECTED_CONTRACT_VERSION:
        raise RuntimeError(f"健康检查契约版本不正确：{payload!r}")
    if str(payload.get("ui_mode") or "") != "default":
        raise RuntimeError(f"健康检查 ui_mode 不正确：{payload!r}")
    return payload


def _assert_runtime_db_path(db_path: str) -> None:
    normalized = _normalize_db_path(db_path)
    if not normalized:
        raise RuntimeError("运行时 DB 契约文件为空。")
    if not os.path.isabs(normalized):
        raise RuntimeError(f"运行时 DB 路径不是绝对路径：{db_path}")
    if not os.path.exists(normalized):
        raise RuntimeError(f"运行时 DB 文件不存在：{normalized}")


def main() -> int:
    if len(sys.argv) < 2:
        print("用法：python validate_dist_exe.py \"dist\\\\排产系统\\\\排产系统.exe\"")
        return 2

    exe_path = os.path.abspath(sys.argv[1])
    if not os.path.exists(exe_path):
        print(f"[validate] exe 不存在：{exe_path}")
        return 2

    print(f"[validate] 启动：{exe_path}")
    cwd = os.path.dirname(exe_path)
    log_dir = os.path.join(cwd, "logs")

    try:
        _clear_runtime_contract_files(log_dir)
    except Exception as e:
        print(f"[validate] 验收失败：{e}")
        return 5

    p = subprocess.Popen(
        [exe_path],
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )

    try:
        host, port, db_path = _wait_for_runtime_contract(log_dir, p, timeout_s=20.0)
        _assert_runtime_db_path(db_path)
        _wait_port_open(host, port, p, timeout_s=20.0)
        _assert_process_running(p, f"运行时端口就绪后进程已退出：{host}:{port}")

        base = f"http://{host}:{port}"
        health = _assert_health(base, timeout=3.0)
        _assert_process_running(p, "健康检查通过后进程已退出。")
        print(f"[validate] runtime -> {host}:{port} db={db_path}")
        print(
            "[validate] health -> "
            f"app={health.get('app')} status={health.get('status')} contract={health.get('contract_version')}"
        )

        urls = [
            ("/", 200),
            ("/personnel/", 200),
            ("/equipment/", 200),
            ("/process/", 200),
            ("/scheduler/", 200),
            ("/system/backup", 200),
        ]
        for path, expect in urls:
            code = _http_get(base + path, timeout=3.0)
            print(f"[validate] GET {path} -> {code}")
            if code != expect:
                print("[validate] 验收失败：页面不可访问。")
                return 6

        _assert_process_running(p, "页面检查通过后进程已退出。")
        print("[validate] 验收通过：exe 冷启动、运行时 host/port/db 契约与健康检查均正常。")
        return 0
    except Exception as e:
        print(f"[validate] 验收失败：{e}")
        return 5
    finally:
        try:
            p.terminate()
            p.wait(timeout=5)
        except Exception as e:
            print(f"[validate] 警告：terminate 失败：{e}")
            try:
                p.kill()
                p.wait(timeout=5)
            except Exception as kill_e:
                print(f"[validate] 警告：kill 失败：{kill_e}")


if __name__ == "__main__":
    raise SystemExit(main())

