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
    回归目标（v4 迁移）：
    - 当 DB 的 SchemaVersion=3 且存在大小写/空格混用的枚举字段时，
      ensure_schema() 会触发 v4 迁移，把这些字段统一清洗为 trim+lower，并对空值写默认值。
    - 迁移前必须生成备份文件，便于失败回滚。
    """
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection

    schema_path = os.path.join(repo_root, "schema.sql")
    tmpdir = tempfile.mkdtemp(prefix="aps_regression_migrate_v4_")
    test_db = os.path.join(tmpdir, "aps_migrate_v4.db")

    # 1) 初始化一个“已是 v3 的库”：SchemaVersion=3，并写入若干大小写/空格混用的枚举字段
    conn0 = sqlite3.connect(test_db)
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            conn0.executescript(f.read())
        conn0.execute("UPDATE SchemaVersion SET version=3 WHERE id=1")

        # Parts（外键前置）
        conn0.execute(
            "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed) VALUES (?,?,?,?)",
            ("P001", "零件", "", " YES "),
        )

        # OpTypes：category（internal/external）
        conn0.execute(
            "INSERT INTO OpTypes (op_type_id, name, category) VALUES (?,?,?)",
            ("OT001", "数铣", " EXTERNAL "),
        )

        # Operator/Machine（为 OperatorMachine 外键前置）
        conn0.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?,?,?)", ("O1", "测试人员", "active"))
        conn0.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?,?,?)", ("M1", "测试设备", "active"))

        # OperatorMachine：skill_level/is_primary
        conn0.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?,?,?,?)",
            ("O1", "M1", " ExPeRt ", " YES "),
        )

        # Batches：priority/ready_status/status
        conn0.execute(
            """
            INSERT INTO Batches (batch_id, part_no, part_name, quantity, priority, ready_status, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("B001", "P001", "零件", 1, " URGENT ", " YES ", " PENDING "),
        )

        # BatchOperations：source/status
        conn0.execute(
            """
            INSERT INTO BatchOperations (op_code, batch_id, seq, op_type_name, source, status, setup_hours, unit_hours)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("B001_01", "B001", 1, "工序A", " INTERNAL  ", " PENDING ", 0.0, 0.0),
        )

        # ExternalGroups：merge_mode
        conn0.execute(
            """
            INSERT INTO ExternalGroups (group_id, part_no, start_seq, end_seq, merge_mode, total_days)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("G001", "P001", 1, 1, " MERGED ", 3.0),
        )

        # WorkCalendar：day_type/allow*
        conn0.execute(
            """
            INSERT INTO WorkCalendar (date, day_type, shift_hours, efficiency, allow_normal, allow_urgent, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("2026-01-01", " WORKDAY ", 8.0, 1.0, " YES ", " NO ", "v4"),
        )

        conn0.commit()
    finally:
        try:
            conn0.close()
        except Exception:
            pass

    # 2) ensure_schema 触发迁移到当前版本（包含 v4 清洗）
    ensure_schema(test_db, logger=None, schema_path=schema_path, backup_dir=None)

    # 3) 断言：字段已被清洗；SchemaVersion >= CURRENT_SCHEMA_VERSION
    conn = get_connection(test_db)
    try:
        rowp = conn.execute("SELECT route_parsed FROM Parts WHERE part_no='P001'").fetchone()
        assert rowp["route_parsed"] == "yes", f"Parts.route_parsed 清洗失败：{rowp['route_parsed']!r}"

        rowot = conn.execute("SELECT category FROM OpTypes WHERE op_type_id='OT001'").fetchone()
        assert rowot["category"] == "external", f"OpTypes.category 清洗失败：{rowot['category']!r}"

        rowom = conn.execute(
            "SELECT skill_level, is_primary FROM OperatorMachine WHERE operator_id='O1' AND machine_id='M1'"
        ).fetchone()
        assert rowom["skill_level"] == "expert", f"OperatorMachine.skill_level 清洗失败：{rowom['skill_level']!r}"
        assert rowom["is_primary"] == "yes", f"OperatorMachine.is_primary 清洗失败：{rowom['is_primary']!r}"

        rowb = conn.execute("SELECT priority, ready_status, status FROM Batches WHERE batch_id='B001'").fetchone()
        assert rowb["priority"] == "urgent", f"Batches.priority 清洗失败：{rowb['priority']!r}"
        assert rowb["ready_status"] == "yes", f"Batches.ready_status 清洗失败：{rowb['ready_status']!r}"
        assert rowb["status"] == "pending", f"Batches.status 清洗失败：{rowb['status']!r}"

        rowop = conn.execute("SELECT source, status FROM BatchOperations WHERE op_code='B001_01'").fetchone()
        assert rowop["source"] == "internal", f"BatchOperations.source 清洗失败：{rowop['source']!r}"
        assert rowop["status"] == "pending", f"BatchOperations.status 清洗失败：{rowop['status']!r}"

        rowg = conn.execute("SELECT merge_mode FROM ExternalGroups WHERE group_id='G001'").fetchone()
        assert rowg["merge_mode"] == "merged", f"ExternalGroups.merge_mode 清洗失败：{rowg['merge_mode']!r}"

        rowc = conn.execute("SELECT day_type, allow_normal, allow_urgent FROM WorkCalendar WHERE date='2026-01-01'").fetchone()
        assert rowc["day_type"] == "workday", f"WorkCalendar.day_type 清洗失败：{rowc['day_type']!r}"
        assert rowc["allow_normal"] == "yes", f"WorkCalendar.allow_normal 清洗失败：{rowc['allow_normal']!r}"
        assert rowc["allow_urgent"] == "no", f"WorkCalendar.allow_urgent 清洗失败：{rowc['allow_urgent']!r}"

        rowv = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        v = int(rowv["version"] if isinstance(rowv, sqlite3.Row) else rowv[0])
        assert v >= CURRENT_SCHEMA_VERSION, f"预期 SchemaVersion>={CURRENT_SCHEMA_VERSION}，实际 {v}"
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # 4) 断言：迁移前备份存在（before_migrate_v3_to_v{CURRENT_SCHEMA_VERSION}）
    backups_dir = os.path.join(os.path.dirname(os.path.abspath(test_db)), "backups")
    assert os.path.isdir(backups_dir), f"预期备份目录存在：{backups_dir}"
    expected_suffix = f"before_migrate_v3_to_v{CURRENT_SCHEMA_VERSION}"
    backup_files = [f for f in os.listdir(backups_dir) if f.startswith("aps_backup_") and expected_suffix in f and f.endswith(".db")]
    assert backup_files, f"未找到迁移前备份文件（dir={backups_dir}）"

    print("OK")


if __name__ == "__main__":
    main()

