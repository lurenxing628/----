"""
冒烟测试：app_new_ui create_app 基础可用性。

旧的 smoke_* 脚本不会被 pytest 默认收集；这个 regression_* 文件保留同等保护，
并让全量 pytest 能自动覆盖这条入口。
"""

from __future__ import annotations


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
    r1 = client.get("/")
    if r1.status_code != 200:
        raise RuntimeError(f"GET / 返回非 200：{r1.status_code}")

    r2 = client.get("/excel-demo/")
    if r2.status_code != 200:
        raise RuntimeError(f"GET /excel-demo/ 返回非 200：{r2.status_code}")
