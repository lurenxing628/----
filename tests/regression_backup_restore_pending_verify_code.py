from __future__ import annotations

import os
import sqlite3
import sys
import tempfile


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

    from core.infrastructure.backup import BackupManager

    tmpdir = tempfile.mkdtemp(prefix="aps_reg_restore_pending_verify_")
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
    assert os.path.exists(backup_path), f"备份文件未生成：{backup_path}"

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DELETE FROM Demo")
        conn.execute("INSERT INTO Demo (name) VALUES (?)", ("mutated",))
        conn.commit()
    finally:
        conn.close()

    result = manager.restore(backup_path)
    assert result.ok is True, result
    assert result.code == "copied_pending_verify", f"恢复完成后应先进入 copied_pending_verify，实际 {result.code!r}"
    assert result.before_restore_path, "恢复前快照路径不应为空"
    assert os.path.exists(result.before_restore_path), f"恢复前快照缺失：{result.before_restore_path}"
    assert "等待后续结构校验" in str(result.message), result.message

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT name FROM Demo ORDER BY id LIMIT 1").fetchone()
    finally:
        conn.close()
    assert row is not None and row[0] == "before", f"数据库内容未恢复到备份状态：{row!r}"

    print("OK")


if __name__ == "__main__":
    main()
