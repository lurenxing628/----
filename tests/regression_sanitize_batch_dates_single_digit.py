"""回归测试：旧库（SchemaVersion=0）迁移清洗时，Batches.due_date 等 DATE 字段允许单数字月/日（如 2026-1-1），并稳定归一化为补零 ISO（2026-01-01），同时升级到当前 schema 版本。"""

import os
import sqlite3


def test_sanitize_batch_dates_single_digit(tmp_path, schema_path):
    """
    回归目标：
    - 旧库迁移清洗时，DATE 字段允许单数字月/日（例如 2026-1-1），并稳定归一化为 ISO（2026-01-01）。
    """


    from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection

    tmpdir = str(tmp_path)
    test_db = os.path.join(tmpdir, "aps_sanitize_batch_dates_old.db")
    backup_dir = os.path.join(tmpdir, "backups_migrate")
    os.makedirs(backup_dir, exist_ok=True)

    # 1) 构造完整旧库：结构完整但版本停在 v0，用单数字日期触发 v1 清洗
    conn0 = sqlite3.connect(test_db)
    try:
        conn0.execute("PRAGMA foreign_keys = OFF;")
        with open(schema_path, "r", encoding="utf-8") as f:
            conn0.executescript(f.read())
        conn0.execute("UPDATE SchemaVersion SET version=0 WHERE id=1")
        conn0.execute("INSERT INTO Parts (part_no, part_name) VALUES (?, ?)", ("P1", "Part1"))
        conn0.execute(
            "INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date) VALUES (?, ?, ?, ?, ?)",
            ("B001", "P1", "Part1", 1, "2026-1-1"),
        )
        conn0.commit()
    finally:
        try:
            conn0.close()
        except Exception:
            pass

    # 2) 执行 ensure_schema：应触发迁移并清洗 due_date
    ensure_schema(test_db, logger=None, schema_path=schema_path, backup_dir=backup_dir)

    # 3) 断言：due_date 被归一化为 ISO（补零）
    conn = get_connection(test_db)
    try:
        row = conn.execute("SELECT due_date FROM Batches WHERE batch_id = ?", ("B001",)).fetchone()
        assert row, "未找到测试批次 B001"
        due = row["due_date"] if isinstance(row, sqlite3.Row) else row[0]
        # 说明：项目已开启 sqlite3 类型探测（PARSE_DECLTYPES），因此 DATE 可能自动转换为 datetime.date
        if hasattr(due, "isoformat"):
            due_text = due.isoformat()
        else:
            due_text = str(due)
        assert due_text == "2026-01-01", f"预期 due_date='2026-01-01'，实际 {due!r}"

        # 附加断言：缺整表被补齐后，应继续迁移到当前版本
        rowv = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        v = int(rowv["version"] if isinstance(rowv, sqlite3.Row) else rowv[0])
        assert v >= CURRENT_SCHEMA_VERSION, f"预期 SchemaVersion 升到当前版本，实际 {v}"
    finally:
        try:
            conn.close()
        except Exception:
            pass


