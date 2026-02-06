"""
回归测试：当 APS_DB_PATH 是纯文件名（不含目录）时，create_app() 不应崩溃。

历史问题：
- app.py / app_new_ui.py 曾在启动时执行 os.makedirs(os.path.dirname(DATABASE_PATH))
- 若 APS_DB_PATH="aps_test.db"（dirname 为空串），Windows 上会触发 FileNotFoundError，导致启动失败
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

    # 在临时目录内运行，确保：DB 文件落在 tmpdir/ 下且不会污染仓库目录
    tmpdir = tempfile.mkdtemp(prefix="aps_regression_dbpath_")
    old_cwd = os.getcwd()
    try:
        os.chdir(tmpdir)

        os.environ["APS_ENV"] = "development"
        os.environ["APS_DB_PATH"] = "aps_test.db"  # 关键：无目录
        os.environ["APS_LOG_DIR"] = str(Path(tmpdir) / "logs")
        os.environ["APS_BACKUP_DIR"] = str(Path(tmpdir) / "backups")
        os.environ["APS_EXCEL_TEMPLATE_DIR"] = str(Path(tmpdir) / "templates_excel")

        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

        # 注意：app.py import 时会执行 create_app()（并创建全局 app），环境变量已提前设置，影响可控。
        app_mod = importlib.import_module("app")
        _app = app_mod.create_app()

        expected_db = os.path.join(tmpdir, "aps_test.db")
        if not os.path.exists(expected_db):
            raise RuntimeError(f"DB 未在预期位置创建：{expected_db}")

        # 额外断言：flask app 对象存在（避免未来 create_app 被改成返回 None）
        if _app is None:
            raise RuntimeError("create_app() 返回 None")

        print("OK")
        print(expected_db)
    finally:
        try:
            os.chdir(old_cwd)
        except Exception:
            pass


if __name__ == "__main__":
    main()

