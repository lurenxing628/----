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
    """
    回归目标：
    - 对“不完整旧库”显式 fail-fast 时，不应每次调用 ensure_schema() 都先生成迁移前备份。
    - 同一个 stuck DB 连续执行两次 ensure_schema()，都应直接报契约错误且不产生 before_migrate 备份风暴。
    """

    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import MigrationContractError, ensure_schema, get_connection

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_migration_failfast_no_backup_")
    test_db = os.path.join(tmpdir, "aps_failfast.db")
    backup_dir = os.path.join(tmpdir, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    conn0 = sqlite3.connect(test_db)
    try:
        conn0.execute("PRAGMA foreign_keys = OFF;")
        conn0.executescript(
            """
            CREATE TABLE SchemaVersion (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version INTEGER NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO SchemaVersion (id, version) VALUES (1, 3);

            CREATE TABLE Batches (
                batch_id TEXT PRIMARY KEY,
                part_no TEXT NOT NULL,
                part_name TEXT,
                quantity INTEGER NOT NULL,
                priority TEXT DEFAULT 'normal',
                ready_status TEXT DEFAULT 'yes'
            );
            """
        )
        conn0.execute(
            "INSERT INTO Batches (batch_id, part_no, part_name, quantity, priority, ready_status) VALUES (?, ?, ?, ?, ?, ?)",
            ("B001", "P1", "零件", 1, " URGENT ", " YES "),
        )
        conn0.commit()
    finally:
        conn0.close()

    for _ in range(2):
        try:
            ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"), backup_dir=backup_dir)
        except MigrationContractError as e:
            msg = str(e)
            assert "不受支持的残缺结构" in msg, msg
        else:
            raise AssertionError("预期复杂残缺库直接 fail-fast，但 ensure_schema() 实际成功返回")

    backup_files = [
        name
        for name in os.listdir(backup_dir)
        if name.startswith("aps_backup_") and "before_migrate" in name and name.endswith(".db")
    ]
    assert not backup_files, f"fail-fast 预检不应生成迁移前备份，实际 {backup_files}"

    conn = get_connection(test_db)
    try:
        row = conn.execute("SELECT priority, ready_status FROM Batches WHERE batch_id='B001'").fetchone()
        assert row is not None, "未找到测试批次 B001"
        assert row["priority"] == " URGENT ", f"fail-fast 后不应留下部分清洗，实际 {row['priority']!r}"
        assert row["ready_status"] == " YES ", f"fail-fast 后不应留下部分清洗，实际 {row['ready_status']!r}"
        rowv = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        version = int(rowv["version"] if isinstance(rowv, sqlite3.Row) else rowv[0])
        assert version == 3, f"预期 SchemaVersion 保持 3，实际 {version}"
    finally:
        conn.close()

    print("OK")


if __name__ == "__main__":
    main()
