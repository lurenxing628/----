"""
回归测试：app_new_ui 在未显式提供 SECRET_KEY 时，运行时仍应确保 SECRET_KEY 可用。
"""

from __future__ import annotations


def test_app_new_ui_secret_key_runtime_ensure(db_env, monkeypatch) -> None:
    import importlib
    import sys

    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delitem(sys.modules, "app_new_ui", raising=False)
    mod = importlib.import_module("app_new_ui")
    app = mod.create_app()

    key = app.config.get("SECRET_KEY")
    if not key or not str(key).strip():
        raise RuntimeError("app_new_ui.create_app() 未确保 SECRET_KEY")
