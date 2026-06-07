"""
回归测试：当 APS_DB_PATH 是纯文件名（不含目录）时，create_app() 不应崩溃。

历史问题：
- app.py / app_new_ui.py 曾在启动时执行 os.makedirs(os.path.dirname(DATABASE_PATH))
- 若 APS_DB_PATH="aps_test.db"（dirname 为空串），Windows 上会触发 FileNotFoundError，导致启动失败
"""

from __future__ import annotations

import os


def test_app_db_path_no_dirname(tmp_path, monkeypatch) -> None:
    import importlib

    # 在临时目录内运行，确保：DB 文件落在 tmp_path/ 下且不会污染仓库目录
    monkeypatch.chdir(tmp_path)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", "aps_test.db")  # 关键：无目录
    monkeypatch.setenv("APS_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("APS_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(tmp_path / "templates_excel"))

    # 注意：app.py import 时会执行 create_app()（并创建全局 app），环境变量已提前设置，影响可控。
    app_mod = importlib.import_module("app")
    _app = app_mod.create_app()

    expected_db = os.path.join(str(tmp_path), "aps_test.db")
    if not os.path.exists(expected_db):
        raise RuntimeError(f"DB 未在预期位置创建：{expected_db}")

    # 额外断言：flask app 对象存在（避免未来 create_app 被改成返回 None）
    if _app is None:
        raise RuntimeError("create_app() 返回 None")
