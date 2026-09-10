"""合同测试：restore 恢复前完整性校验（B05，2026-07-19 盲区扫描）——把备份文件盖到主库前必须先过
PRAGMA integrity_check（与创建侧 backup() 的校验对称，复用同一实现）；备份文件损坏（页可读但内容坏 /
整体不是 sqlite 库）时 fail-loud 拒绝恢复：返回 ok=False、code=backup_integrity_failed、中文可查原因，
主库一个字节都不得被改动；校验点位于 _copy_db_file 源侧，自动回滚消费 before_restore 快照同受保护。"""

from __future__ import annotations

import os
import sqlite3
from urllib.parse import unquote

import core.infrastructure.backup as backup_mod
from core.infrastructure.backup import BackupManager


class _CorruptedRowsCursor:
    def fetchall(self):
        return [("*** in database main ***", ), ("row 7 missing from index", )]


class _NotOkConnection(sqlite3.Connection):
    """integrity_check 跑通但结果≠ok：模拟页可解析但 payload 已损坏的备份。"""

    def execute(self, sql, *args, **kwargs):  # type: ignore[override]
        if "integrity_check" in str(sql).lower():
            return _CorruptedRowsCursor()
        return super().execute(sql, *args, **kwargs)


def _sqlite_uri_database_path(database) -> str:
    text = os.fspath(database)
    if not text.startswith("file:"):
        return text
    return unquote(text[5:].split("?", 1)[0])


def _make_manager_with_backup(tmp_path):
    tmpdir = str(tmp_path)
    db_path = os.path.join(tmpdir, "aps_test.db")
    backup_dir = os.path.join(tmpdir, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE Demo (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO Demo (name) VALUES (?)", ("before",))
        conn.commit()
    finally:
        conn.close()
    manager = BackupManager(db_path=db_path, backup_dir=backup_dir, keep_days=7, logger=None)
    backup_path = manager.backup(suffix="manual")

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE Demo SET name = ?", ("mutated",))
        conn.commit()
    finally:
        conn.close()
    return manager, db_path, backup_path


def _read_demo_name(db_path: str) -> str:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT name FROM Demo ORDER BY id LIMIT 1").fetchone()
    finally:
        conn.close()
    return str(row[0]) if row else ""


def test_restore_refuses_file_that_is_not_a_database(tmp_path) -> None:
    """真实损坏形态：备份文件被截断/覆盖成非 sqlite 内容（U 盘拷回截断、位衰减头页损坏）。"""
    manager, db_path, backup_path = _make_manager_with_backup(tmp_path)
    with open(backup_path, "wb") as f:
        f.write(b"this is definitely not a sqlite database " * 64)

    result = manager.restore(backup_path)

    assert result.ok is False
    assert result.code == "backup_integrity_failed", f"实际 code={result.code} message={result.message}"
    assert "拒绝恢复" in str(result.message), result.message
    assert _read_demo_name(db_path) == "mutated", "拒绝恢复后主库必须保持原样（不得落地损坏库）"


def test_restore_refuses_backup_failing_integrity_result(tmp_path, monkeypatch) -> None:
    """payload 级损坏：integrity_check 跑通但结果≠ok，同样必须拒绝恢复。"""
    manager, db_path, backup_path = _make_manager_with_backup(tmp_path)

    real_connect = sqlite3.connect

    def fake_connect(path, *args, **kwargs):
        # 只对恢复源（用户选定的备份文件）注入坏校验结果；主库与 before_restore 快照连接保持原生。
        if _sqlite_uri_database_path(path) == os.path.abspath(backup_path):
            kwargs.setdefault("factory", _NotOkConnection)
        return real_connect(path, *args, **kwargs)

    monkeypatch.setattr(backup_mod.sqlite3, "connect", fake_connect)

    result = manager.restore(backup_path)

    assert result.ok is False
    assert result.code == "backup_integrity_failed", f"实际 code={result.code} message={result.message}"
    assert "完整性检查未通过" in str(result.message), result.message
    # 校验发生在 source.backup(dest) 之前：主库未被改动，且恢复前快照已生成（可供人工核查）。
    assert _read_demo_name(db_path) == "mutated"
    assert result.before_restore_path and os.path.exists(result.before_restore_path)


def test_restore_happy_path_still_restores_after_integrity_check(tmp_path) -> None:
    """防误伤：完好备份照常通过校验并复制成功（copied_pending_verify 语义不变）。"""
    manager, db_path, backup_path = _make_manager_with_backup(tmp_path)

    result = manager.restore(backup_path)

    assert result.ok is True and result.code == "copied_pending_verify", result
    assert _read_demo_name(db_path) == "before", "完好备份应正常恢复到备份时内容"
