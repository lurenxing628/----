"""
回归测试：app_new_ui 在未显式提供 SECRET_KEY 时，运行时仍应确保 SECRET_KEY 可用。
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


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_new_ui_secret_")
    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = str(Path(tmpdir) / "aps_test.db")
    os.environ["APS_LOG_DIR"] = str(Path(tmpdir) / "logs")
    os.environ["APS_BACKUP_DIR"] = str(Path(tmpdir) / "backups")
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = str(Path(tmpdir) / "templates_excel")
    os.environ.pop("SECRET_KEY", None)

    sys.modules.pop("app_new_ui", None)
    mod = importlib.import_module("app_new_ui")
    app = mod.create_app()

    key = app.config.get("SECRET_KEY")
    if not key or not str(key).strip():
        raise RuntimeError("app_new_ui.create_app() 未确保 SECRET_KEY")

    print("OK")


if __name__ == "__main__":
    main()

