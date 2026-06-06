"""
回归测试：app_new_ui 在 SECRET_KEY 提供条件下的 session/flash 合约

验证点：
1) create_app() 后可正常读写 session。
2) flash/get_flashed_messages 可正常工作。
"""

from __future__ import annotations

from flask import flash, get_flashed_messages, jsonify, session


def test_app_new_ui_session_contract(db_env, monkeypatch) -> None:
    import importlib
    import sys

    monkeypatch.setenv("SECRET_KEY", "aps-session-contract-key")
    monkeypatch.delitem(sys.modules, "app_new_ui", raising=False)
    mod = importlib.import_module("app_new_ui")
    app = mod.create_app()

    @app.route("/__session_contract_probe__")
    def _probe():
        session["probe"] = "ok"
        flash("hello")
        msgs = get_flashed_messages()
        return jsonify({"probe": session.get("probe"), "messages": msgs})

    c = app.test_client()
    r = c.get("/__session_contract_probe__")
    if r.status_code != 200:
        raise RuntimeError(f"探针接口返回非 200：{r.status_code}")
    data = r.get_json(silent=True) or {}
    if data.get("probe") != "ok":
        raise RuntimeError(f"session 写入/读取异常：{data}")
    msgs = data.get("messages") or []
    if "hello" not in msgs:
        raise RuntimeError(f"flash/get_flashed_messages 异常：{data}")
