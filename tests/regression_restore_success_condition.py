from __future__ import annotations

import importlib
import os
import sqlite3
import sys
import tempfile
from unittest import mock


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _assert_status(resp, name: str, expect: int = 200) -> str:
    if resp.status_code != expect:
        body = resp.data.decode("utf-8", errors="ignore") if getattr(resp, "data", None) else ""
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect}，body={body[:500]}")
    return resp.data.decode("utf-8", errors="ignore")


def _restore_log_count(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT COUNT(1) FROM OperationLogs WHERE module='system' AND action='restore'").fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


class _FakeManager:
    def __init__(self, result):
        self._result = result

    def restore(self, _backup_path):
        return self._result

    def list_backups(self):
        return []


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.backup import RestoreResult
    from core.infrastructure.database import ensure_schema

    root = tempfile.mkdtemp(prefix="aps_reg_restore_success_")
    test_db = os.path.join(root, "aps_test.db")
    test_logs = os.path.join(root, "logs")
    test_backups = os.path.join(root, "backups")
    test_templates = os.path.join(root, "templates_excel")
    os.makedirs(test_logs, exist_ok=True)
    os.makedirs(test_backups, exist_ok=True)
    os.makedirs(test_templates, exist_ok=True)

    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = test_db
    os.environ["APS_LOG_DIR"] = test_logs
    os.environ["APS_BACKUP_DIR"] = test_backups
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = test_templates

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"), backup_dir=test_backups)

    backup_filename = "aps_backup_20260318_120000_manual.db"
    backup_path = os.path.join(test_backups, backup_filename)
    with open(backup_path, "wb") as f:
        f.write(b"fake")

    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    client = app.test_client()

    with mock.patch(
        "web.routes.system_backup._get_backup_manager",
        return_value=_FakeManager(
            RestoreResult(ok=True, code="success", message="restore ok", before_restore_path=os.path.join(test_backups, "aps_backup_before.db"))
        ),
    ), mock.patch("web.routes.system_backup.ensure_schema", side_effect=RuntimeError("boom")):
        html = _assert_status(
            client.post("/system/backup/restore", data={"filename": backup_filename}, follow_redirects=True),
            "POST /system/backup/restore (ensure_schema fail)",
        )
        if "数据库文件已恢复，但后续结构检查失败，请查看日志后再继续使用。" not in html:
            raise RuntimeError("ensure_schema 失败后未看到错误提示")
        if f"已从备份恢复：{backup_filename}" in html:
            raise RuntimeError("ensure_schema 失败后不应再显示 success flash")
        if _restore_log_count(test_db) != 0:
            raise RuntimeError("ensure_schema 失败后不应写入 restore success 日志")

    with mock.patch(
        "web.routes.system_backup._get_backup_manager",
        return_value=_FakeManager(
            RestoreResult(
                ok=False,
                code="restore_failed_rolled_back",
                message="数据库恢复失败，但已自动回滚到恢复前备份：aps_backup_before_restore.db。",
            )
        ),
    ) as mgr_patch, mock.patch("web.routes.system_backup.ensure_schema") as ensure_patch:
        html = _assert_status(
            client.post("/system/backup/restore", data={"filename": backup_filename}, follow_redirects=True),
            "POST /system/backup/restore (rolled back)",
        )
        if "数据库恢复失败，但已自动回滚到恢复前备份：aps_backup_before_restore.db。" not in html:
            raise RuntimeError("未看到 restore_failed_rolled_back 的专属提示")
        if f"已从备份恢复：{backup_filename}" in html:
            raise RuntimeError("restore_failed_rolled_back 不应显示 success flash")
        if not mgr_patch.called:
            raise RuntimeError("预期 restore manager 被调用")
        if ensure_patch.called:
            raise RuntimeError("restore 失败后不应继续执行 ensure_schema")

    with mock.patch(
        "web.routes.system_backup._get_backup_manager",
        return_value=_FakeManager(
            RestoreResult(
                ok=False,
                code="restore_failed_rollback_failed",
                message="数据库恢复失败，且自动回滚也失败了，请立即检查日志并手动校验数据库。",
            )
        ),
    ), mock.patch("web.routes.system_backup.ensure_schema") as ensure_patch:
        html = _assert_status(
            client.post("/system/backup/restore", data={"filename": backup_filename}, follow_redirects=True),
            "POST /system/backup/restore (rollback failed)",
        )
        if "数据库恢复失败，且自动回滚也失败了，请立即检查日志并手动校验数据库。" not in html:
            raise RuntimeError("未看到 restore_failed_rollback_failed 的专属提示")
        if f"已从备份恢复：{backup_filename}" in html:
            raise RuntimeError("restore_failed_rollback_failed 不应显示 success flash")
        if ensure_patch.called:
            raise RuntimeError("restore 失败后不应继续执行 ensure_schema")

    print("OK")


if __name__ == "__main__":
    main()
