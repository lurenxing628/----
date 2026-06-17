"""回归测试：当 SchemaVersion=1 但 v2 目标表 WorkCalendar 缺失时，ensure_schema() 须判为残缺结构并 fail-fast（不用当前 schema.sql 静默补回整表再迁移成功），且 fail-fast 发生在迁移备份前——版本保持 1、不补回 WorkCalendar、不生成 before_migrate 备份风暴。"""

import os
import sqlite3


def test_migration_outcome_skip_no_upgrade(tmp_path, schema_path) -> None:
    """
    回归目标：
    - 当 SchemaVersion=1，但 v2 目标表 WorkCalendar 缺失时，
      ensure_schema() 应把数据库判为残缺结构并 fail-fast。
    - 不允许先按当前 schema.sql 补回缺失整表，再把坏库迁到当前版本。
    - fail-fast 发生在迁移备份前，避免反复调用制造备份风暴。
    """

    from core.infrastructure.database import MigrationContractError, ensure_schema, get_connection

    tmpdir = str(tmp_path)
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
