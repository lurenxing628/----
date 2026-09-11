"""
冒烟测试：app_new_ui create_app 基础可用性。

旧的 smoke_* 脚本不会被 pytest 默认收集；这个 regression_* 文件保留同等保护，
并让全量 pytest 能自动覆盖这条入口。
"""

from __future__ import annotations

from tests._support.workbench_web_contract import canonical_boot, retired_response


def test_app_new_ui_create_app_smoke(db_env, monkeypatch) -> None:
    import importlib
    import sys

    monkeypatch.setenv("SECRET_KEY", "aps-smoke-app-new-ui-key")
    monkeypatch.delitem(sys.modules, "app_new_ui", raising=False)
    mod = importlib.import_module("app_new_ui")

    app = mod.create_app()
    if app is None:
        raise RuntimeError("app_new_ui.create_app() 返回 None")
    if not hasattr(mod, "app"):
        raise RuntimeError("app_new_ui 未导出模块级 app")
    if mod.app is None:
        raise RuntimeError("app_new_ui 模块级 app 为 None")

    client = app.test_client()
    boot = canonical_boot(client, "/", "dashboard", {})
    assert "dashboard" in boot["enabled_views"]

    r2 = client.get("/excel-demo/")
    retired_response(r2)
