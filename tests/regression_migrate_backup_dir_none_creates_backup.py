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
    - 当 ensure_schema() 触发 DB 迁移，但调用方传入 backup_dir=None 时，
      依然必须在“默认回退备份目录”生成迁移前备份文件，确保失败可回滚。

    复现设计：
    - 构造一个旧库：OperatorMachine 缺少 skill_level/is_primary
    - 调用 ensure_schema(test_db, backup_dir=None) 触发迁移
    - 断言：<db_dir>/backups 下出现 before_migrate_v0_to_v{CURRENT_SCHEMA_VERSION} 的备份文件
    """

    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_migrate_backup_none_")
    test_db = os.path.join(tmpdir, "aps_migrate_backup_none.db")

    # 1) 构造旧库：OperatorMachine 缺列（会导致 _detect_schema_is_current() 返回 False，从而触发迁移）
    conn0 = sqlite3.connect(test_db)
    try:
        conn0.execute("PRAGMA foreign_keys = OFF;")
        conn0.execute(
            """
            CREATE TABLE OperatorMachine (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                operator_id TEXT NOT NULL,
                machine_id  TEXT NOT NULL,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn0.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP001", "MC_A1"))
        conn0.commit()
    finally:
        try:
            conn0.close()
        except Exception:
            pass

    # 2) 执行 ensure_schema：显式传入 backup_dir=None（应回退到 <db_dir>/backups 并强制创建迁移前备份）
    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"), backup_dir=None)

    expected_suffix = f"before_migrate_v0_to_v{CURRENT_SCHEMA_VERSION}"

    # 3) 断言：默认备份目录存在且包含迁移前备份文件
    fallback_backups = os.path.join(os.path.dirname(os.path.abspath(test_db)), "backups")
    assert os.path.isdir(fallback_backups), f"预期默认备份目录存在：{fallback_backups}"

    backup_files = [
        f
        for f in os.listdir(fallback_backups)
        if f.startswith("aps_backup_") and expected_suffix in f and f.endswith(".db")
    ]
    assert backup_files, f"未找到迁移前备份文件（dir={fallback_backups}）"

    # 4) 附加校验：缺整表会被先补齐，再继续迁移到当前版本
    conn = get_connection(test_db)
    try:
        row_cols = conn.execute("PRAGMA table_info(OperatorMachine)").fetchall()
        cols = {r["name"] if isinstance(r, sqlite3.Row) else r[1] for r in row_cols}
        assert {"skill_level", "is_primary"} <= cols, f"预期 OperatorMachine 已补齐关键列，实际 {cols}"
        row = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        v = int(row["version"] if isinstance(row, sqlite3.Row) else row[0])
        assert v >= CURRENT_SCHEMA_VERSION, f"预期 SchemaVersion 升到当前版本，实际 {v}"
    finally:
        try:
            conn.close()
        except Exception:
            pass

    print("OK")


if __name__ == "__main__":
    main()

