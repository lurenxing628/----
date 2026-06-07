"""
回归测试：A06 后 app_new_ui 显式启用安全头与 session cookie 加固。
"""

from __future__ import annotations


def test_app_new_ui_security_hardening_enabled(db_env, monkeypatch) -> None:
    import importlib
    import sys

    monkeypatch.setenv("SECRET_KEY", "aps-new-ui-security-harden-test-key")
    monkeypatch.delitem(sys.modules, "app_new_ui", raising=False)
    mod = importlib.import_module("app_new_ui")
    app = mod.create_app()

    if app.config.get("SESSION_COOKIE_HTTPONLY") is not True:
        raise RuntimeError("A06 回归失败：SESSION_COOKIE_HTTPONLY 未启用")
    if str(app.config.get("SESSION_COOKIE_SAMESITE")) != "Lax":
        raise RuntimeError(f"A06 回归失败：SESSION_COOKIE_SAMESITE 非 Lax，实际={app.config.get('SESSION_COOKIE_SAMESITE')!r}")

    client = app.test_client()
    resp = client.get("/")
    if resp.status_code != 200:
        raise RuntimeError(f"GET / 返回非 200：{resp.status_code}")

    must_headers = {
        "X-Frame-Options": "SAMEORIGIN",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }
    for k, v in must_headers.items():
        got = resp.headers.get(k)
        if got != v:
            raise RuntimeError(f"A06 回归失败：响应头 {k} 期望 {v!r}，实际 {got!r}")
