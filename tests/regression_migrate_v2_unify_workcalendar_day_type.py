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
    回归目标（v2 迁移）：
    - 当 DB 的 SchemaVersion=1 且 WorkCalendar 存在历史 day_type='weekend' 记录时，
      ensure_schema() 会触发 v2 迁移，把 weekend 统一更新为 holiday。
    - 迁移前必须生成备份文件，便于失败回滚。
    """

    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection

    schema_path = os.path.join(repo_root, "schema.sql")
    tmpdir = tempfile.mkdtemp(prefix="aps_regression_migrate_v2_")
    test_db = os.path.join(tmpdir, "aps_migrate_v2.db")

    # 1) 初始化一个“已是 v1 的库”：SchemaVersion=1，并写入一条 weekend
    conn0 = sqlite3.connect(test_db)
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            conn0.executescript(f.read())
        conn0.execute("UPDATE SchemaVersion SET version=1 WHERE id=1")
        conn0.execute(
            """
            INSERT OR REPLACE INTO WorkCalendar (date, day_type, shift_hours, efficiency, allow_normal, allow_urgent, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("2026-01-25", "weekend", 0, 1.0, "no", "no", "old weekend"),
        )
        conn0.commit()
    finally:
        try:
            conn0.close()
        except Exception:
            pass

    # 2) 调用 ensure_schema 触发迁移（当前版本可能为更高版本；会包含 v2 的 weekend->holiday 修正）
    ensure_schema(test_db, logger=None, schema_path=schema_path, backup_dir=None)

    # 3) 断言：weekend 已变为 holiday，且 SchemaVersion >= CURRENT_SCHEMA_VERSION
    conn = get_connection(test_db)
    try:
        row = conn.execute("SELECT day_type FROM WorkCalendar WHERE date='2026-01-25'").fetchone()
        got = row["day_type"] if isinstance(row, sqlite3.Row) else (row[0] if row else None)
        assert got == "holiday", f"预期 day_type=holiday，实际 {got}"

        rowv = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        v = int(rowv["version"] if isinstance(rowv, sqlite3.Row) else rowv[0])
        assert v >= CURRENT_SCHEMA_VERSION, f"预期 SchemaVersion>={CURRENT_SCHEMA_VERSION}，实际 {v}"
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # 4) 断言：迁移前备份存在（before_migrate_v1_to_v{CURRENT_SCHEMA_VERSION}）
    backups_dir = os.path.join(os.path.dirname(os.path.abspath(test_db)), "backups")
    assert os.path.isdir(backups_dir), f"预期备份目录存在：{backups_dir}"
    expected_suffix = f"before_migrate_v1_to_v{CURRENT_SCHEMA_VERSION}"
    backup_files = [
        f for f in os.listdir(backups_dir) if f.startswith("aps_backup_") and expected_suffix in f and f.endswith(".db")
    ]
    assert backup_files, f"未找到迁移前备份文件（dir={backups_dir}）"

    print("OK")


if __name__ == "__main__":
    main()

