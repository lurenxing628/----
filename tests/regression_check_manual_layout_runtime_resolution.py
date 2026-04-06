"""
回归测试：check_manual_layout 运行时 base URL 解析契约。

验证点：
1) 优先读取运行时 `logs/aps_host.txt` / `logs/aps_port.txt`。
2) `--base-url` 显式值优先于运行时文件。
3) 缺少运行时文件时回退到默认 `http://127.0.0.1:5000`。
4) 可用服务判断改为依赖 `/system/health`。
5) `/system/health` 必须满足 `contract_version=1` 才算可用。
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _load_module(repo_root: str):
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("check_manual_layout", None)
    return importlib.import_module("check_manual_layout")


def _write_runtime_files(runtime_dir: Path, host: str, port: int) -> None:
    log_dir = runtime_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "aps_host.txt").write_text(host + "\n", encoding="utf-8")
    (log_dir / "aps_port.txt").write_text(str(port) + "\n", encoding="utf-8")


class _HealthHandler(BaseHTTPRequestHandler):
    payload = {"app": "aps", "status": "ok", "contract_version": 1}

    def do_GET(self) -> None:
        if self.path != "/system/health":
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps(self.payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # type: ignore[override]
        return


class _HealthServer:
    def __init__(self, payload: dict) -> None:
        self.payload = dict(payload)
        self.httpd: HTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.port = 0

    def __enter__(self):
        _HealthHandler.payload = dict(self.payload)
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
    mod = _load_module(repo_root)

    with _HealthServer({"app": "aps", "status": "ok", "contract_version": 1}) as server:
        runtime_dir = Path(tempfile.mkdtemp(prefix="aps_manual_layout_runtime_"))
        _write_runtime_files(runtime_dir, "127.0.0.1", server.port)

        base_url, source = mod._resolve_base_url(None, runtime_dir=runtime_dir)
        _assert(base_url == f"http://127.0.0.1:{server.port}", "运行时文件解析的 base_url 不正确")
        _assert(source == "runtime_files", "运行时文件解析的 source 不正确")
        _assert(mod._server_is_reachable(base_url) is True, "健康 APS 实例应可达")

    explicit_url, explicit_source = mod._resolve_base_url("http://127.0.0.1:5705/", runtime_dir=Path(tempfile.mkdtemp()))
    _assert(explicit_url == "http://127.0.0.1:5705", "显式 base_url 未正确规范化")
    _assert(explicit_source == "explicit", "显式 base_url 应优先返回 explicit source")

    fallback_url, fallback_source = mod._resolve_base_url(None, runtime_dir=Path(tempfile.mkdtemp(prefix="aps_manual_layout_default_")))
    _assert(fallback_url == mod._DEFAULT_BASE_URL, "缺少运行时文件时应回退到默认地址")
    _assert(fallback_source == "default", "缺少运行时文件时 source 应为 default")

    with _HealthServer({"app": "aps", "status": "ok"}) as legacy_server:
        _assert(
            mod._server_is_reachable(f"http://127.0.0.1:{legacy_server.port}") is False,
            "缺少 contract_version 的健康响应不应被接受",
        )

    with _HealthServer({"app": "other", "status": "ok", "contract_version": 1}) as other_server:
        _assert(
            mod._server_is_reachable(f"http://127.0.0.1:{other_server.port}") is False,
            "非 APS 健康响应不应被接受",
        )

    print("OK")


if __name__ == "__main__":
    main()
