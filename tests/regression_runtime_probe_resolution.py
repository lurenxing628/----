"""
回归测试：runtime_probe 运行时 endpoint 解析契约。

验证点：
1) `read_runtime_host_port()` / `delete_stale_runtime_files()` 正确处理运行时文件。
2) `probe_health()` 仅接受 `app=aps`、`status=ok` 且 `contract_version=1` 的健康响应。
3) `resolve_healthy_endpoint()` 按 `preferred -> runtime_files` 顺序解析。
4) `wait_for_healthy_runtime_endpoint()` 能等待健康实例就绪。
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _load_runtime_probe(repo_root: str):
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("web.bootstrap.runtime_probe", None)
    return importlib.import_module("web.bootstrap.runtime_probe")


def _write_runtime_files(runtime_dir: str, host: str, port: int | str) -> None:
    log_dir = os.path.join(runtime_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    with open(os.path.join(log_dir, "aps_host.txt"), "w", encoding="utf-8") as f:
        f.write(str(host).strip() + "\n")
    with open(os.path.join(log_dir, "aps_port.txt"), "w", encoding="utf-8") as f:
        f.write(str(port).strip() + "\n")
    with open(os.path.join(log_dir, "aps_db_path.txt"), "w", encoding="utf-8") as f:
        f.write(os.path.normcase(os.path.abspath(os.path.join(runtime_dir, "runtime.db"))) + "\n")


class _HealthHandler(BaseHTTPRequestHandler):
    payload = {"app": "aps", "status": "ok", "contract_version": 1}
    status_code = 200

    def do_GET(self) -> None:
        if self.path != "/system/health":
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps(self.payload, ensure_ascii=False).encode("utf-8")
        self.send_response(self.status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # type: ignore[override]
        return


class _HealthServer:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.payload = dict(payload)
        self.status_code = int(status_code)
        self.httpd: HTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.port = 0

    def __enter__(self):
        _HealthHandler.payload = dict(self.payload)
        _HealthHandler.status_code = self.status_code
        self.httpd = HTTPServer(("127.0.0.1", 0), _HealthHandler)
        self.port = int(self.httpd.server_address[1])
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
        if self.thread is not None:
            self.thread.join(timeout=2)


def main() -> None:
    repo_root = find_repo_root()
    runtime_probe = _load_runtime_probe(repo_root)

    tmpdir = tempfile.mkdtemp(prefix="aps_runtime_probe_")
    with _HealthServer(
        {
            "app": "aps",
            "status": "ok",
            "contract_version": 1,
            "ui_mode": "default",
            "timestamp": "2026-03-16T00:00:00Z",
        }
    ) as server:
        _write_runtime_files(tmpdir, "127.0.0.1", server.port)

        _assert(
            runtime_probe.build_base_url("127.0.0.1", server.port) == f"http://127.0.0.1:{server.port}",
            "build_base_url 返回值不正确",
        )
        _assert(
            runtime_probe.read_runtime_host_port(tmpdir) == ("127.0.0.1", server.port),
            "read_runtime_host_port 未正确解析运行时文件",
        )
        _assert(
            runtime_probe.read_runtime_db_path(tmpdir)
            == os.path.normcase(os.path.abspath(os.path.join(tmpdir, "runtime.db"))),
            "read_runtime_db_path 未正确解析运行时文件",
        )

        health = runtime_probe.probe_health(f"http://127.0.0.1:{server.port}", timeout=2.0)
        _assert(bool(health), "probe_health 未识别健康 APS 实例")

        preferred = runtime_probe.resolve_healthy_endpoint(
            tmpdir,
            preferred_host="127.0.0.1",
            preferred_port=server.port,
            timeout=2.0,
        )
        _assert(bool(preferred), "resolve_healthy_endpoint 未识别 preferred 实例")
        _assert(preferred["source"] == "preferred", "preferred 实例未优先返回")

        runtime_only = runtime_probe.resolve_healthy_endpoint(tmpdir, timeout=2.0)
        _assert(bool(runtime_only), "resolve_healthy_endpoint 未识别 runtime_files 实例")
        _assert(runtime_only["source"] == "runtime_files", "runtime_files source 不正确")

        waited = runtime_probe.wait_for_healthy_runtime_endpoint(tmpdir, timeout_s=2, interval_s=0.1)
        _assert(int(waited["port"]) == server.port, "wait_for_healthy_runtime_endpoint 返回的端口不正确")

        runtime_probe.delete_stale_runtime_files(tmpdir)
        _assert(runtime_probe.read_runtime_host_port(tmpdir) is None, "delete_stale_runtime_files 未删除运行时文件")
        _assert(runtime_probe.read_runtime_db_path(tmpdir) is None, "delete_stale_runtime_files 未删除 db_path 文件")
        runtime_probe.delete_stale_runtime_files(tmpdir)

    bad_tmpdir = tempfile.mkdtemp(prefix="aps_runtime_probe_bad_")
    _write_runtime_files(bad_tmpdir, "127.0.0.1", "not_a_port")
    _assert(runtime_probe.read_runtime_host_port(bad_tmpdir) is None, "非法端口文件不应被解析")

    missing_tmpdir = tempfile.mkdtemp(prefix="aps_runtime_probe_missing_")
    _assert(runtime_probe.read_runtime_host_port(missing_tmpdir) is None, "缺失运行时文件时应返回 None")

    with _HealthServer({"app": "other", "status": "ok"}) as non_aps_server:
        non_aps = runtime_probe.probe_health(f"http://127.0.0.1:{non_aps_server.port}", timeout=2.0)
        _assert(non_aps is None, "非 APS 健康响应不应被接受")

    with _HealthServer({"app": "aps", "status": "ok", "contract_version": 2}) as wrong_contract_server:
        wrong_contract = runtime_probe.probe_health(f"http://127.0.0.1:{wrong_contract_server.port}", timeout=2.0)
        _assert(wrong_contract is None, "错误 contract_version 的健康响应不应被接受")

    print("OK")


if __name__ == "__main__":
    main()
