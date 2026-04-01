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
    - 当 SchemaVersion=1，但 v2 目标表 WorkCalendar 缺失时，
      ensure_schema() 应先按 schema.sql 补回缺失整表，再继续迁移到当前版本。
    - 迁移前备份仍必须生成。
    """
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection

    schema_path = os.path.join(repo_root, "schema.sql")
    tmpdir = tempfile.mkdtemp(prefix="aps_regression_migration_skip_")
    test_db = os.path.join(tmpdir, "aps_migration_skip.db")
    backup_dir = os.path.join(tmpdir, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    conn0 = sqlite3.connect(test_db)
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            conn0.executescript(f.read())
        conn0.execute("UPDATE SchemaVersion SET version=1 WHERE id=1")
        conn0.execute("DROP TABLE WorkCalendar")
        conn0.commit()
    finally:
        try:
            conn0.close()
        except Exception:
            pass

    ensure_schema(test_db, logger=None, schema_path=schema_path, backup_dir=backup_dir)

    conn = get_connection(test_db)
    try:
        row_wc = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='WorkCalendar'"
        ).fetchone()
        assert row_wc is not None, "预期 WorkCalendar 已被受控补齐"
        row = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        version = int(row["version"] if isinstance(row, sqlite3.Row) else row[0])
        assert version >= CURRENT_SCHEMA_VERSION, f"预期最终迁移到当前版本，实际 {version}"
    finally:
        try:
            conn.close()
        except Exception:
            pass

    expected_suffix = f"before_migrate_v1_to_v{CURRENT_SCHEMA_VERSION}"
    backup_files = [
        name
        for name in os.listdir(backup_dir)
        if name.startswith("aps_backup_") and expected_suffix in name and name.endswith(".db")
    ]
    assert backup_files, f"未找到迁移前备份文件（dir={backup_dir}）"

    print("OK")


if __name__ == "__main__":
    main()
