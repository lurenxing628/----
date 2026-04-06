"""
回归测试：A06 后 app_new_ui 显式启用安全头与 session cookie 加固。
"""

from __future__ import annotations

import importlib
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
    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = str(Path(tmpdir) / "aps_test.db")
    os.environ["APS_LOG_DIR"] = str(Path(tmpdir) / "logs")
    os.environ["APS_BACKUP_DIR"] = str(Path(tmpdir) / "backups")
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = str(Path(tmpdir) / "templates_excel")
    os.environ["SECRET_KEY"] = "aps-new-ui-security-harden-test-key"


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_new_ui_security_")
    _prepare_env(tmpdir)

    sys.modules.pop("app_new_ui", None)
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

    print("OK")


if __name__ == "__main__":
    main()

