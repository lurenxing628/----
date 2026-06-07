"""回归测试：当 ensure_schema() 触发旧库迁移、但调用方显式传入 backup_dir=None 时，必须回退到 <db_dir>/backups 并强制生成迁移前备份文件（before_migrate_v4_to_v{CURRENT}），并完成枚举值规范化（熟练→expert、是→yes）升至当前版本。"""

import os
import sqlite3


def test_migrate_backup_dir_none_creates_backup(tmp_path, schema_path):
    """
    回归目标：
    - 当 ensure_schema() 触发 DB 迁移，但调用方传入 backup_dir=None 时，
      依然必须在“默认回退备份目录”生成迁移前备份文件，确保失败可回滚。

    复现设计：
    - 构造一个完整旧库：SchemaVersion=4，OperatorMachine 仍有 v5 前的旧枚举值
    - 调用 ensure_schema(test_db, backup_dir=None) 触发迁移
    - 断言：<db_dir>/backups 下出现 before_migrate_v4_to_v{CURRENT_SCHEMA_VERSION} 的备份文件
    """


    from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection

    tmpdir = str(tmp_path)
    test_db = os.path.join(tmpdir, "aps_migrate_backup_none.db")


    # 1) 构造完整旧库：结构完整但版本停在 v4，用旧枚举值触发后续迁移
    conn0 = sqlite3.connect(test_db)
    try:
        conn0.execute("PRAGMA foreign_keys = OFF;")
        with open(schema_path, "r", encoding="utf-8") as f:
            conn0.executescript(f.read())
        conn0.execute("UPDATE SchemaVersion SET version=4 WHERE id=1")
        conn0.execute("INSERT INTO Operators (operator_id, name) VALUES (?, ?)", ("OP001", "张三"))
        conn0.execute("INSERT INTO Machines (machine_id, name) VALUES (?, ?)", ("MC_A1", "一号设备"))
        conn0.execute(
            """
            INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary)
            VALUES (?, ?, ?, ?)
            """,
            ("OP001", "MC_A1", "熟练", "是"),
        )
        conn0.commit()
    finally:
        try:
            conn0.close()
        except Exception:
            pass

    # 2) 执行 ensure_schema：显式传入 backup_dir=None（应回退到 <db_dir>/backups 并强制创建迁移前备份）
    ensure_schema(test_db, logger=None, schema_path=schema_path, backup_dir=None)

    expected_suffix = f"before_migrate_v4_to_v{CURRENT_SCHEMA_VERSION}"

    # 3) 断言：默认备份目录存在且包含迁移前备份文件
    fallback_backups = os.path.join(os.path.dirname(os.path.abspath(test_db)), "backups")
    assert os.path.isdir(fallback_backups), f"预期默认备份目录存在：{fallback_backups}"

    backup_files = [
        f
        for f in os.listdir(fallback_backups)
        if f.startswith("aps_backup_") and expected_suffix in f and f.endswith(".db")
    ]
    assert backup_files, f"未找到迁移前备份文件（dir={fallback_backups}）"

    # 4) 附加校验：完整旧库正常迁移到当前版本，旧枚举值被规范化
    conn = get_connection(test_db)
    try:
        row_om = conn.execute(
            """
            SELECT skill_level, is_primary
            FROM OperatorMachine
            WHERE operator_id = 'OP001' AND machine_id = 'MC_A1'
            """
        ).fetchone()
        assert row_om is not None, "未找到 OperatorMachine 迁移结果"
        assert row_om["skill_level"] == "expert", f"预期 skill_level='expert'，实际 {row_om['skill_level']!r}"
        assert row_om["is_primary"] == "yes", f"预期 is_primary='yes'，实际 {row_om['is_primary']!r}"
        row = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        v = int(row["version"] if isinstance(row, sqlite3.Row) else row[0])
        assert v >= CURRENT_SCHEMA_VERSION, f"预期 SchemaVersion 升到当前版本，实际 {v}"
    finally:
        try:
            conn.close()
        except Exception:
            pass


