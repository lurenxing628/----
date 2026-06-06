"""回归测试：POST /system/backup/restore 仅在恢复成功且 ensure_schema 结构校验通过（verified）时才展示成功 flash 并写入一条 restore success 日志（detail 含 restore_code=verified/filename/before_restore_filename）；ensure_schema 失败回滚、回滚也失败、恢复失败已回滚、恢复失败回滚失败这四类结局都展示对应专属提示、不显示成功 flash、且不写 success 日志。"""

from __future__ import annotations

import json
import os
import sqlite3
from unittest import mock


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


def _latest_restore_log_detail(db_path: str):
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT detail FROM OperationLogs WHERE module='system' AND action='restore' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None or row[0] is None:
            return None
        raw = str(row[0]).strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return raw
    finally:
        conn.close()


class _FakeManager:
    def __init__(self, result, rollback_result=None):
        self._result = result
        self._rollback_result = rollback_result

    def restore(self, _backup_path):
        return self._result

    def _auto_rollback(self, _before_restore_path, **_kwargs):
        return self._rollback_result

    def list_backups(self):
        return []


def test_restore_success_condition(app_client, db_env) -> None:
    from core.infrastructure.backup import RestoreResult

    test_db = db_env
    test_backups = os.environ["APS_BACKUP_DIR"]

    backup_filename = "aps_backup_20260318_120000_manual.db"
    backup_path = os.path.join(test_backups, backup_filename)
    with open(backup_path, "wb") as f:
        f.write(b"fake")

    client = app_client

    before_restore_path = os.path.join(test_backups, "aps_backup_before.db")
    with open(before_restore_path, "wb") as f:
        f.write(b"before")

    success_before_count = _restore_log_count(test_db)
    with mock.patch(
        "web.routes.system_backup._get_backup_manager",
        return_value=_FakeManager(
            RestoreResult(ok=True, code="copied_pending_verify", message="restore copied", before_restore_path=before_restore_path)
        ),
    ), mock.patch("web.routes.system_backup.ensure_schema") as ensure_patch:
        html = _assert_status(
            client.post("/system/backup/restore", data={"filename": backup_filename}, follow_redirects=True),
            "POST /system/backup/restore (verified)",
        )
        if f"已从备份恢复并完成结构校验：{backup_filename}。建议刷新页面/重新打开浏览器以加载最新数据。" not in html:
            raise RuntimeError("verified 成功后未看到结构校验完成提示")
        if ensure_patch.call_count != 1:
            raise RuntimeError(f"verified 成功后 ensure_schema 调用次数不正确：{ensure_patch.call_count}")
        if _restore_log_count(test_db) != success_before_count + 1:
            raise RuntimeError("verified 成功后应写入一条 restore success 日志")
        detail = _latest_restore_log_detail(test_db)
        if not isinstance(detail, dict):
            raise RuntimeError(f"restore success 日志 detail 应为 JSON 对象，实际={detail!r}")
        if str(detail.get("restore_code") or "") != "verified":
            raise RuntimeError(f"restore success 日志未写入 verified：{detail!r}")
        if str(detail.get("filename") or "") != backup_filename:
            raise RuntimeError(f"restore success 日志 filename 不正确：{detail!r}")
        if str(detail.get("before_restore_filename") or "") != "aps_backup_before.db":
            raise RuntimeError(f"restore success 日志 before_restore_filename 不正确：{detail!r}")

    fail_before_count = _restore_log_count(test_db)
    with mock.patch(
        "web.routes.system_backup._get_backup_manager",
        return_value=_FakeManager(
            RestoreResult(ok=True, code="copied_pending_verify", message="restore copied", before_restore_path=before_restore_path),
            rollback_result=RestoreResult(
                ok=False,
                code="verify_failed_rolled_back",
                message="数据库结构校验失败，但已自动回滚到恢复前备份：aps_backup_before.db。",
                before_restore_path=before_restore_path,
            ),
        ),
    ), mock.patch("web.routes.system_backup.ensure_schema", side_effect=RuntimeError("boom")):
        html = _assert_status(
            client.post("/system/backup/restore", data={"filename": backup_filename}, follow_redirects=True),
            "POST /system/backup/restore (ensure_schema fail rolled back)",
        )
        if "数据库结构校验失败，但已自动回滚到恢复前备份：aps_backup_before.db。" not in html:
            raise RuntimeError("ensure_schema 失败后未看到自动回滚提示")
        if f"已从备份恢复：{backup_filename}" in html:
            raise RuntimeError("ensure_schema 失败后不应再显示 success flash")
        if _restore_log_count(test_db) != fail_before_count:
            raise RuntimeError("ensure_schema 失败后不应写入 restore success 日志")

    rollback_fail_before_count = _restore_log_count(test_db)
    with mock.patch(
        "web.routes.system_backup._get_backup_manager",
        return_value=_FakeManager(
            RestoreResult(ok=True, code="copied_pending_verify", message="restore copied", before_restore_path=before_restore_path),
            rollback_result=RestoreResult(
                ok=False,
                code="verify_failed_rollback_failed",
                message="数据库结构校验失败，且自动回滚也失败了，请立即检查日志并手动校验数据库。",
                before_restore_path=before_restore_path,
            ),
        ),
    ), mock.patch("web.routes.system_backup.ensure_schema", side_effect=RuntimeError("boom")):
        html = _assert_status(
            client.post("/system/backup/restore", data={"filename": backup_filename}, follow_redirects=True),
            "POST /system/backup/restore (ensure_schema fail rollback failed)",
        )
        if "数据库结构校验失败，且自动回滚也失败了，请立即检查日志并手动校验数据库。" not in html:
            raise RuntimeError("ensure_schema 失败后未看到回滚失败提示")
        if _restore_log_count(test_db) != rollback_fail_before_count:
            raise RuntimeError("verify_failed_rollback_failed 不应写入 restore success 日志")

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
        rolled_back_before_count = _restore_log_count(test_db)
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
        if _restore_log_count(test_db) != rolled_back_before_count:
            raise RuntimeError("restore_failed_rolled_back 不应写入 restore success 日志")

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
        rollback_failed_before_count = _restore_log_count(test_db)
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
        if _restore_log_count(test_db) != rollback_failed_before_count:
            raise RuntimeError("restore_failed_rollback_failed 不应写入 restore success 日志")
