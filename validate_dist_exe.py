"""
打包后 exe 冷启动验收脚本（用于 Win7/离线交付验收）。

用法：
  python validate_dist_exe.py "dist\\排产系统\\排产系统.exe"

验证点（最小闭环）：
  - 进程可启动
  - 本地端口可访问（GET / 返回 200）
  - 可访问关键页面（/personnel/ /equipment/ /process/ /scheduler/ /system/backup）

注意：
  - 该脚本会启动 exe 并在验证后结束进程
  - 若 5000 端口被占用，会直接失败（请先关闭占用进程）
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request


def _is_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
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


def main() -> int:
    if len(sys.argv) < 2:
        print("用法：python validate_dist_exe.py \"dist\\\\排产系统\\\\排产系统.exe\"")
        return 2

    exe_path = sys.argv[1]
    exe_path = os.path.abspath(exe_path)
    if not os.path.exists(exe_path):
        print(f"[validate] exe 不存在：{exe_path}")
        return 2

    host = "127.0.0.1"
    port = 5000

    if _is_port_open(host, port):
        print(f"[validate] 端口 {port} 已被占用，请先关闭占用进程后重试。")
        return 3

    print(f"[validate] 启动：{exe_path}")
    # 在 exe 所在目录启动，确保相对目录（db/logs/backups/templates_excel）落在交付目录下
    cwd = os.path.dirname(exe_path)

    p = subprocess.Popen(
        [exe_path],
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )

    try:
        # 等待服务启动（最多 20 秒）
        t0 = time.time()
        ready = False
        while time.time() - t0 < 20:
            if p.poll() is not None:
                print(f"[validate] 进程提前退出（exit_code={p.returncode}），请检查 logs/aps_error.log")
                return 4
            if _is_port_open(host, port):
                ready = True
                break
            time.sleep(0.3)

        if not ready:
            print("[validate] 超时：服务未在 20 秒内启动。请检查 logs/aps_error.log")
            return 5

        base = f"http://{host}:{port}"
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

        print("[validate] 验收通过：exe 冷启动与关键页面可访问。")
        return 0
    finally:
        try:
            # 尽量正常结束；若失败则强杀
            p.terminate()
            p.wait(timeout=5)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())

