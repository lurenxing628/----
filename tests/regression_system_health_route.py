"""
回归测试：system 健康检查路由契约。

验证点：
1) `app.py` / `app_new_ui.py` 均暴露 `GET /system/health`。
2) 返回 JSON 包含 app/status/contract_version/ui_mode/timestamp。
3) 请求健康检查时不打开 `g.db` / `g.op_logger`。
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


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_system_health_")
    _prepare_env(tmpdir)

    app_mod = _load_module("app")
    app_new_ui_mod = _load_module("app_new_ui")
    factory_mod = importlib.import_module("web.bootstrap.factory")

    _assert_health(app_mod.create_app(), "default", factory_mod)
    _assert_health(app_new_ui_mod.create_app(), "new_ui", factory_mod)
    print("OK")


if __name__ == "__main__":
    main()
