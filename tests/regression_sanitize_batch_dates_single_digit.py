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


def main():
    """
    回归目标：
    - 旧库迁移清洗时，DATE 字段允许单数字月/日（例如 2026-1-1），并稳定归一化为 ISO（2026-01-01）。
    """

    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_sanitize_batch_dates_")
    test_db = os.path.join(tmpdir, "aps_sanitize_batch_dates_old.db")
    backup_dir = os.path.join(tmpdir, "backups_migrate")
    os.makedirs(backup_dir, exist_ok=True)

    # 1) 构造旧库：Batches 缺少 ready_date（会触发 v0->v1 迁移中的 _sanitize_batch_dates）
    conn0 = sqlite3.connect(test_db)
    try:
        conn0.execute("PRAGMA foreign_keys = OFF;")
        conn0.executescript(
            """
            CREATE TABLE Batches (
                batch_id        TEXT PRIMARY KEY,
                part_no         TEXT NOT NULL,
                part_name       TEXT,
                quantity        INTEGER NOT NULL,
                due_date        DATE,
                priority        TEXT DEFAULT 'normal',
                ready_status    TEXT DEFAULT 'yes',
                status          TEXT DEFAULT 'pending',
                remark          TEXT
            );
            """
        )
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
    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"), backup_dir=backup_dir)

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

    print("OK")


if __name__ == "__main__":
    main()

