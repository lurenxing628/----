from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from typing import Optional, Tuple


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _fetch_link(conn: sqlite3.Connection, operator_id: str, machine_id: str) -> Tuple[Optional[str], Optional[str]]:
    row = conn.execute(
        "SELECT skill_level, is_primary FROM OperatorMachine WHERE operator_id=? AND machine_id=?",
        (operator_id, machine_id),
    ).fetchone()
    if row is None:
        raise AssertionError(f"未找到关联：{operator_id}/{machine_id}")
    if isinstance(row, sqlite3.Row):
        return row["skill_level"], row["is_primary"]
    return row[0], row[1]


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection

    schema_path = os.path.join(repo_root, "schema.sql")
    tmpdir = tempfile.mkdtemp(prefix="aps_regression_migrate_v5_")
    test_db = os.path.join(tmpdir, "aps_migrate_v5.db")

    conn0 = sqlite3.connect(test_db)
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            conn0.executescript(f.read())
        conn0.execute("UPDATE SchemaVersion SET version=4 WHERE id=1")
        conn0.execute("INSERT INTO Operators (operator_id, name) VALUES (?, ?)", ("OP100", "测试员甲"))
        conn0.execute("INSERT INTO Operators (operator_id, name) VALUES (?, ?)", ("OP200", "测试员乙"))
        conn0.execute("INSERT INTO Operators (operator_id, name) VALUES (?, ?)", ("OP300", "测试员丙"))
        conn0.execute("INSERT INTO Operators (operator_id, name) VALUES (?, ?)", ("OP400", "测试员丁"))
        conn0.execute("INSERT INTO Machines (machine_id, name) VALUES (?, ?)", ("MC100", "设备甲"))
        conn0.execute("INSERT INTO Machines (machine_id, name) VALUES (?, ?)", ("MC200", "设备乙"))
        conn0.execute("INSERT INTO Machines (machine_id, name) VALUES (?, ?)", ("MC300", "设备丙"))
        conn0.execute("INSERT INTO Machines (machine_id, name) VALUES (?, ?)", ("MC400", "设备丁"))
        conn0.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
            ("OP100", "MC100", "熟练", "是"),
        )
        conn0.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
            ("OP200", "MC200", "", ""),
        )
        conn0.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
            ("OP300", "MC300", "普通", "否"),
        )
        conn0.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
            ("OP400", "MC400", "初级", "主"),
        )
        conn0.commit()
    finally:
        try:
            conn0.close()
        except Exception:
            pass

    ensure_schema(test_db, logger=None, schema_path=schema_path, backup_dir=None)

    conn = get_connection(test_db)
    try:
        skill1, primary1 = _fetch_link(conn, "OP100", "MC100")
        assert skill1 == "expert", f"预期 OP100/MC100.skill_level=expert，实际 {skill1!r}"
        assert primary1 == "yes", f"预期 OP100/MC100.is_primary=yes，实际 {primary1!r}"

        skill2, primary2 = _fetch_link(conn, "OP200", "MC200")
        assert skill2 == "normal", f"预期 OP200/MC200.skill_level=normal，实际 {skill2!r}"
        assert primary2 == "no", f"预期 OP200/MC200.is_primary=no，实际 {primary2!r}"

        skill3, primary3 = _fetch_link(conn, "OP300", "MC300")
        assert skill3 == "normal", f"预期 OP300/MC300.skill_level=normal，实际 {skill3!r}"
        assert primary3 == "no", f"预期 OP300/MC300.is_primary=no，实际 {primary3!r}"

        skill4, primary4 = _fetch_link(conn, "OP400", "MC400")
        assert skill4 == "beginner", f"预期 OP400/MC400.skill_level=beginner，实际 {skill4!r}"
        assert primary4 == "yes", f"预期 OP400/MC400.is_primary=yes，实际 {primary4!r}"

        rowv = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        version = int(rowv["version"] if isinstance(rowv, sqlite3.Row) else rowv[0])
        assert version >= CURRENT_SCHEMA_VERSION, f"预期 SchemaVersion>={CURRENT_SCHEMA_VERSION}，实际 {version}"
    finally:
        try:
            conn.close()
        except Exception:
            pass

    backups_dir = os.path.join(os.path.dirname(os.path.abspath(test_db)), "backups")
    assert os.path.isdir(backups_dir), f"预期备份目录存在：{backups_dir}"
    expected_suffix = f"before_migrate_v4_to_v{CURRENT_SCHEMA_VERSION}"
    backup_files = [
        name
        for name in os.listdir(backups_dir)
        if name.startswith("aps_backup_") and expected_suffix in name and name.endswith(".db")
    ]
    assert backup_files, f"未找到迁移前备份文件（dir={backups_dir}）"

    print("OK")


if __name__ == "__main__":
    main()
