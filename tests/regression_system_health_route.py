"""
回归测试：system 健康检查路由契约。

验证点：
1) `app.py` / `app_new_ui.py` 均暴露 `GET /system/health`。
2) 返回 JSON 包含 app/status/contract_version/ui_mode/timestamp。
3) 请求健康检查时不打开 `g.db` / `g.op_logger`。
4) `POST /system/runtime/shutdown` 仅允许本机 + 正确 token，且不打开数据库连接。
5) `request_runtime_server_shutdown()` 返回 False 时应返回 503 + `shutdown_unavailable`。
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
from pathlib import Path


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _prepare_env(tmpdir: str) -> None:
    os.environ["APS_ENV"] = "production"
    os.environ["APS_DB_PATH"] = str(Path(tmpdir) / "aps.db")
    os.environ["APS_LOG_DIR"] = str(Path(tmpdir) / "logs")
    os.environ["APS_BACKUP_DIR"] = str(Path(tmpdir) / "backups")
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = str(Path(tmpdir) / "templates_excel")
    os.environ["SECRET_KEY"] = "aps-health-contract-test-key"


def _load_module(name: str):
    sys.modules.pop(name, None)
    return importlib.import_module(name)


def _assert_health(app, expected_ui_mode: str, factory_mod) -> None:
    get_connection_calls = []
    original_get_connection = factory_mod.get_connection

    def _fail_get_connection(*args, **kwargs):
        get_connection_calls.append((args, kwargs))
        raise RuntimeError("健康检查不应触发数据库连接")

    factory_mod.get_connection = _fail_get_connection
    try:
        with app.test_client() as client:
            resp = client.get("/system/health")
            if resp.status_code != 200:
                raise RuntimeError(f"GET /system/health 返回非 200：{resp.status_code}")

            content_type = str(resp.headers.get("Content-Type") or "")
            if "application/json" not in content_type:
                raise RuntimeError(f"Content-Type 非 JSON：{content_type!r}")

            payload = json.loads(resp.get_data(as_text=True))
            if payload.get("app") != "aps":
                raise RuntimeError(f"app 标识不正确：{payload!r}")
            if payload.get("status") != "ok":
                raise RuntimeError(f"status 不正确：{payload!r}")
            if int(payload.get("contract_version") or 0) != 1:
                raise RuntimeError(f"contract_version 不正确：{payload!r}")
            if str(payload.get("ui_mode") or "") != expected_ui_mode:
                raise RuntimeError(f"ui_mode 不正确：{payload!r}")
            if not str(payload.get("timestamp") or "").strip():
                raise RuntimeError(f"timestamp 为空：{payload!r}")

            if get_connection_calls:
                raise RuntimeError("健康检查不应打开数据库连接")
    finally:
        factory_mod.get_connection = original_get_connection


def _assert_runtime_shutdown(app, system_health_mod, factory_mod) -> None:
    get_connection_calls = []
    shutdown_calls = []
    unavailable_calls = []
    original_get_connection = factory_mod.get_connection
    original_request_runtime_server_shutdown = factory_mod.request_runtime_server_shutdown

    def _fail_get_connection(*args, **kwargs):
        get_connection_calls.append((args, kwargs))
        raise RuntimeError("停机路由不应触发数据库连接")

    def _fake_request_runtime_server_shutdown(logger=None):
        shutdown_calls.append(bool(logger))
        return True

    def _fake_request_runtime_server_shutdown_unavailable(logger=None):
        unavailable_calls.append(bool(logger))
        return False

    factory_mod.get_connection = _fail_get_connection
    factory_mod.request_runtime_server_shutdown = _fake_request_runtime_server_shutdown
    app.config["APS_RUNTIME_SHUTDOWN_TOKEN"] = "aps-shutdown-route-token"
    try:
        with app.test_client() as client:
            forbidden_remote = client.post(
                "/system/runtime/shutdown",
                headers={"X-APS-Shutdown-Token": "aps-shutdown-route-token"},
                environ_overrides={"REMOTE_ADDR": "10.0.0.8"},
            )
            if forbidden_remote.status_code != 403:
                raise RuntimeError(f"非本机地址不应触发停机：{forbidden_remote.status_code}")

            forbidden_token = client.post(
                "/system/runtime/shutdown",
                headers={"X-APS-Shutdown-Token": "wrong-token"},
                environ_overrides={"REMOTE_ADDR": "127.0.0.1"},
            )
            if forbidden_token.status_code != 403:
                raise RuntimeError(f"错误 token 不应触发停机：{forbidden_token.status_code}")

            ok_resp = client.post(
                "/system/runtime/shutdown",
                headers={"X-APS-Shutdown-Token": "aps-shutdown-route-token"},
                environ_overrides={"REMOTE_ADDR": "127.0.0.1"},
            )
            if ok_resp.status_code != 202:
                raise RuntimeError(f"合法停机请求应返回 202：{ok_resp.status_code}")
            payload = json.loads(ok_resp.get_data(as_text=True))
            if payload.get("status") != "shutting_down":
                raise RuntimeError(f"停机路由返回值不正确：{payload!r}")

            if not shutdown_calls:
                raise RuntimeError("合法停机请求未触发 request_runtime_server_shutdown")
            if get_connection_calls:
                raise RuntimeError("停机路由不应打开数据库连接")

            factory_mod.request_runtime_server_shutdown = _fake_request_runtime_server_shutdown_unavailable
            unavailable_resp = client.post(
                "/system/runtime/shutdown",
                headers={"X-APS-Shutdown-Token": "aps-shutdown-route-token"},
                environ_overrides={"REMOTE_ADDR": "127.0.0.1"},
            )
            if unavailable_resp.status_code != 503:
                raise RuntimeError(f"停机不可用时应返回 503：{unavailable_resp.status_code}")
            payload = json.loads(unavailable_resp.get_data(as_text=True))
            if payload.get("status") != "shutdown_unavailable":
                raise RuntimeError(f"停机不可用分支返回值不正确：{payload!r}")

            if not unavailable_calls:
                raise RuntimeError("503 分支未触发 request_runtime_server_shutdown")
            if get_connection_calls:
                raise RuntimeError("停机不可用分支不应打开数据库连接")
    finally:
        factory_mod.get_connection = original_get_connection
        factory_mod.request_runtime_server_shutdown = original_request_runtime_server_shutdown


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_system_health_")
    _prepare_env(tmpdir)

    app_mod = _load_module("app")
    app_new_ui_mod = _load_module("app_new_ui")
    factory_mod = importlib.import_module("web.bootstrap.factory")
    system_health_mod = importlib.import_module("web.routes.system_health")

    _assert_health(app_mod.create_app(), "default", factory_mod)
    _assert_health(app_new_ui_mod.create_app(), "new_ui", factory_mod)
    _assert_runtime_shutdown(app_mod.create_app(), system_health_mod, factory_mod)
    _assert_runtime_shutdown(app_new_ui_mod.create_app(), system_health_mod, factory_mod)
    print("OK")


if __name__ == "__main__":
    main()
