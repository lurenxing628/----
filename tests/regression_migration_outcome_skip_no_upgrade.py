"""回归测试：当 SchemaVersion=1 但 v2 目标表 WorkCalendar 缺失时，ensure_schema() 须判为残缺结构并 fail-fast（不用当前 schema.sql 静默补回整表再迁移成功），且 fail-fast 发生在迁移备份前——版本保持 1、不补回 WorkCalendar、不生成 before_migrate 备份风暴。"""

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
      ensure_schema() 应把数据库判为残缺结构并 fail-fast。
    - 不允许先按当前 schema.sql 补回缺失整表，再把坏库迁到当前版本。
    - fail-fast 发生在迁移备份前，避免反复调用制造备份风暴。
    """
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import MigrationContractError, ensure_schema, get_connection

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

    try:
        ensure_schema(test_db, logger=None, schema_path=schema_path, backup_dir=backup_dir)
    except MigrationContractError as exc:
        message = str(exc)
        assert "不受支持的残缺结构" in message, message
        assert "不会用当前 schema.sql 静默补齐缺失整表" in message, message
    else:
        raise AssertionError("缺失 WorkCalendar 的低版本坏库不应被静默补表并迁移成功")

    conn = get_connection(test_db)
    try:
        row_wc = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='WorkCalendar'"
        ).fetchone()
        assert row_wc is None, "fail-fast 后不应补回 WorkCalendar"
        row = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        version = int(row["version"] if isinstance(row, sqlite3.Row) else row[0])
        assert version == 1, f"fail-fast 后 SchemaVersion 应保持 1，实际 {version}"
    finally:
        try:
            conn.close()
        except Exception:
            pass

    backup_files = [
        name
        for name in os.listdir(backup_dir)
        if name.startswith("aps_backup_") and "before_migrate" in name and name.endswith(".db")
    ]
    assert not backup_files, f"fail-fast 预检不应生成迁移前备份，实际 {backup_files}"

    print("OK")


if __name__ == "__main__":
    main()
