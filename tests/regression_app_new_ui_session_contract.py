"""
回归测试：app_new_ui 在 SECRET_KEY 提供条件下的 session/flash 合约

验证点：
1) create_app() 后可正常读写 session。
2) flash/get_flashed_messages 可正常工作。
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path

from flask import flash, get_flashed_messages, jsonify, session


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
    os.environ["SECRET_KEY"] = "aps-session-contract-key"


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_new_ui_session_")
    _prepare_env(tmpdir)

    sys.modules.pop("app_new_ui", None)
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

    print("OK")


if __name__ == "__main__":
    main()
