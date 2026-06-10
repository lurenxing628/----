"""回归测试（F3 修复）：BackupManager.restore() 在「恢复前保护快照」创建/校验失败时，
必须显式区分为 code=pre_restore_snapshot_failed（而非笼统 restore_failed），中止恢复、
原数据库一字未动、before_restore_path 为空。

背景：恢复前 self.backup(suffix="before_restore") 若因完整性校验失败抛 RuntimeError，
旧实现会落入 restore() 的 catch-all，被收成笼统「数据库恢复失败，请查看日志。」，用户分不清
是「恢复前快照没通过」还是「恢复本身失败」，也不知道原库其实没被动过。本测试钉死区分语义。
此外 MaintenanceWindowError（busy/锁）不得被误并入快照失败分支。"""

from __future__ import annotations

import os
import sqlite3

from core.infrastructure.backup import BackupManager, MaintenanceWindowError


def _make_db_with_row(db_path: str, name: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS Demo (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO Demo (name) VALUES (?)", (name,))
        conn.commit()
    finally:
        conn.close()


def test_restore_pre_snapshot_failure_aborts_and_keeps_db(tmp_path, monkeypatch) -> None:
    tmpdir = str(tmp_path)
    db_path = os.path.join(tmpdir, "aps_test.db")
    backup_dir = os.path.join(tmpdir, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    _make_db_with_row(db_path, "before")
    manager = BackupManager(db_path=db_path, backup_dir=backup_dir, keep_days=7, logger=None)
    # 先用正常路径生成一个可恢复的备份
    backup_path = manager.backup(suffix="manual")
    assert os.path.exists(backup_path), f"备份文件未生成：{backup_path}"

    # 把库改脏，用于验证恢复未发生
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DELETE FROM Demo")
        conn.execute("INSERT INTO Demo (name) VALUES (?)", ("mutated",))
        conn.commit()
    finally:
        conn.close()

    # 让「恢复前保护快照」创建失败（模拟完整性校验执行失败抛裸 RuntimeError）
    orig_backup = manager.backup

    def _boom_before_restore(suffix=None):
        if suffix == "before_restore":
            raise RuntimeError("备份后的数据库完整性检查执行失败（视为不可信备份，不落地）：模拟")
        return orig_backup(suffix=suffix)

    monkeypatch.setattr(manager, "backup", _boom_before_restore)

    result = manager.restore(backup_path)

    assert result.ok is False, result
    assert result.code == "pre_restore_snapshot_failed", (
        f"恢复前快照失败必须区分语义、不得笼统 restore_failed，实际 {result.code!r}"
    )
    assert "恢复前" in str(result.message) and "未改动" in str(result.message), result.message
    assert result.before_restore_path is None, "快照未生成时 before_restore_path 应为空"

    # 原库一字未动：仍是 mutated（恢复被中止在 _copy_db_file 之前）
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT name FROM Demo ORDER BY id LIMIT 1").fetchone()
    finally:
        conn.close()
    assert row is not None and row[0] == "mutated", f"恢复应被中止、原库不应被改动，实际 {row!r}"


def test_restore_pre_snapshot_maintenance_error_not_misclassified(tmp_path, monkeypatch) -> None:
    """MaintenanceWindowError（busy/锁）不得被误并入快照失败分支，须走维护锁语义。"""
    tmpdir = str(tmp_path)
    db_path = os.path.join(tmpdir, "aps_test.db")
    backup_dir = os.path.join(tmpdir, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    _make_db_with_row(db_path, "before")
    manager = BackupManager(db_path=db_path, backup_dir=backup_dir, keep_days=7, logger=None)
    backup_path = manager.backup(suffix="manual")

    def _busy(suffix=None):
        raise MaintenanceWindowError("busy", "数据库正在维护/恢复中，请稍后重试。")

    monkeypatch.setattr(manager, "backup", _busy)
    result = manager.restore(backup_path)
    assert result.code == "busy", (
        f"维护锁应走 busy 语义、不得被当快照失败 pre_restore_snapshot_failed，实际 {result.code!r}"
    )
