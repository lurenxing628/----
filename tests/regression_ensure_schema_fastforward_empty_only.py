from __future__ import annotations

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


def _version_of(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        if row is None:
            raise AssertionError("缺少 SchemaVersion.id=1")
        return int(row[0])
    finally:
        conn.close()


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection

    schema_path = os.path.join(repo_root, "schema.sql")

    empty_root = tempfile.mkdtemp(prefix="aps_reg_schema_empty_")
    empty_db = os.path.join(empty_root, "aps_empty.db")
    empty_backups = os.path.join(empty_root, "backups")
    os.makedirs(empty_backups, exist_ok=True)

    ensure_schema(empty_db, logger=None, schema_path=schema_path, backup_dir=empty_backups)

    empty_version = _version_of(empty_db)
    assert empty_version == CURRENT_SCHEMA_VERSION, f"预期 fresh 空库直接 fast-forward 到 {CURRENT_SCHEMA_VERSION}，实际 {empty_version}"
    empty_backup_files = [
        name
        for name in os.listdir(empty_backups)
        if name.startswith("aps_backup_") and "before_migrate" in name and name.endswith(".db")
    ]
    assert not empty_backup_files, f"预期 fresh 空库不产生迁移前备份，实际 {empty_backup_files}"

    nonempty_root = tempfile.mkdtemp(prefix="aps_reg_schema_nonempty_")
    nonempty_db = os.path.join(nonempty_root, "aps_nonempty.db")
    nonempty_backups = os.path.join(nonempty_root, "backups")
    os.makedirs(nonempty_backups, exist_ok=True)

    conn0 = sqlite3.connect(nonempty_db)
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            conn0.executescript(f.read())
        conn0.execute("UPDATE SchemaVersion SET version=0 WHERE id=1")
        conn0.execute("INSERT INTO Operators (operator_id, name) VALUES (?, ?)", ("OP100", "测试员甲"))
        conn0.execute("INSERT INTO Machines (machine_id, name) VALUES (?, ?)", ("MC100", "设备甲"))
        conn0.execute(
            """
            INSERT INTO WorkCalendar (date, day_type, shift_hours, efficiency, allow_normal, allow_urgent, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("2026-03-01", "weekend", 0, 1.0, " YES ", " NO ", "legacy global"),
        )
        conn0.execute(
            """
            INSERT INTO OperatorCalendar (operator_id, date, day_type, shift_hours, efficiency, allow_normal, allow_urgent, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("OP100", "2026-03-02", "weekend", 0, 1.0, " YES ", " NO ", "legacy operator"),
        )
        conn0.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
            ("OP100", "MC100", "熟练", "是"),
        )
        conn0.commit()
    finally:
        conn0.close()

    ensure_schema(nonempty_db, logger=None, schema_path=schema_path, backup_dir=nonempty_backups)

    conn = get_connection(nonempty_db)
    try:
        row_wc = conn.execute(
            "SELECT day_type, allow_normal, allow_urgent FROM WorkCalendar WHERE date='2026-03-01'"
        ).fetchone()
        assert row_wc is not None, "未找到 WorkCalendar 迁移结果"
        assert row_wc["day_type"] == "holiday", f"预期 WorkCalendar.day_type=holiday，实际 {row_wc['day_type']!r}"
        assert row_wc["allow_normal"] == "yes", f"预期 WorkCalendar.allow_normal=yes，实际 {row_wc['allow_normal']!r}"
        assert row_wc["allow_urgent"] == "no", f"预期 WorkCalendar.allow_urgent=no，实际 {row_wc['allow_urgent']!r}"

        row_oc = conn.execute(
            "SELECT day_type, allow_normal, allow_urgent FROM OperatorCalendar WHERE operator_id='OP100' AND date='2026-03-02'"
        ).fetchone()
        assert row_oc is not None, "未找到 OperatorCalendar 迁移结果"
        assert row_oc["day_type"] == "holiday", f"预期 OperatorCalendar.day_type=holiday，实际 {row_oc['day_type']!r}"
        assert row_oc["allow_normal"] == "yes", f"预期 OperatorCalendar.allow_normal=yes，实际 {row_oc['allow_normal']!r}"
        assert row_oc["allow_urgent"] == "no", f"预期 OperatorCalendar.allow_urgent=no，实际 {row_oc['allow_urgent']!r}"

        row_om = conn.execute(
            "SELECT skill_level, is_primary FROM OperatorMachine WHERE operator_id='OP100' AND machine_id='MC100'"
        ).fetchone()
        assert row_om is not None, "未找到 OperatorMachine 迁移结果"
        assert row_om["skill_level"] == "expert", f"预期 OperatorMachine.skill_level=expert，实际 {row_om['skill_level']!r}"
        assert row_om["is_primary"] == "yes", f"预期 OperatorMachine.is_primary=yes，实际 {row_om['is_primary']!r}"

        row_v = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        version = int(row_v["version"])
        assert version >= CURRENT_SCHEMA_VERSION, f"预期 SchemaVersion>={CURRENT_SCHEMA_VERSION}，实际 {version}"
    finally:
        conn.close()

    expected_suffix = f"before_migrate_v0_to_v{CURRENT_SCHEMA_VERSION}"
    nonempty_backup_files = [
        name
        for name in os.listdir(nonempty_backups)
        if name.startswith("aps_backup_") and expected_suffix in name and name.endswith(".db")
    ]
    assert nonempty_backup_files, f"预期存在迁移前备份（suffix={expected_suffix}），实际为空"

    print("OK")


if __name__ == "__main__":
    main()
