from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from datetime import date, datetime
from typing import Any


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _value(row: Any, key: str):
    if isinstance(row, sqlite3.Row):
        return row[key]
    return row[0]


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection
    from core.services.report.calculations import capacity_hours
    from core.services.scheduler import CalendarService

    schema_path = os.path.join(repo_root, "schema.sql")
    tmpdir = tempfile.mkdtemp(prefix="aps_reg_shift_hours_roundtrip_")
    test_db = os.path.join(tmpdir, "aps_shift_hours.db")

    ensure_schema(test_db, logger=None, schema_path=schema_path, backup_dir=None)

    conn = get_connection(test_db)
    try:
        conn.execute("INSERT INTO Operators (operator_id, name) VALUES (?, ?)", ("OP100", "测试员甲"))
        conn.commit()

        cal_svc = CalendarService(conn, logger=None, op_logger=None)

        cal_svc.upsert(
            "2026-02-10",
            day_type="holiday",
            shift_hours=0,
            efficiency=1.0,
            allow_normal="no",
            allow_urgent="no",
            remark="global zero",
        )
        row0 = conn.execute("SELECT shift_hours FROM WorkCalendar WHERE date=?", ("2026-02-10",)).fetchone()
        assert row0 is not None, "未写入 WorkCalendar 记录"
        assert float(_value(row0, "shift_hours")) == 0.0, f"预期 WorkCalendar.raw shift_hours=0，实际 {_value(row0, 'shift_hours')!r}"
        cal0 = cal_svc.get("2026-02-10")
        assert float(cal0.shift_hours) == 0.0, f"预期 WorkCalendar.get().shift_hours=0，实际 {cal0.shift_hours!r}"
        policy0 = cal_svc.policy_for_datetime(datetime(2026, 2, 10, 9, 0, 0))
        assert float(policy0.shift_hours) == 0.0, f"预期 policy.shift_hours=0，实际 {policy0.shift_hours!r}"
        assert capacity_hours(cal_svc, date(2026, 2, 10), date(2026, 2, 10)) == 0.0, "预期停工日 capacity_hours=0"

        cal_svc.upsert_operator_calendar(
            operator_id="OP100",
            date_value="2026-02-11",
            day_type="holiday",
            shift_hours=0,
            efficiency=1.0,
            allow_normal="no",
            allow_urgent="no",
            remark="operator zero",
        )
        row1 = conn.execute(
            "SELECT shift_hours FROM OperatorCalendar WHERE operator_id=? AND date=?",
            ("OP100", "2026-02-11"),
        ).fetchone()
        assert row1 is not None, "未写入 OperatorCalendar 记录"
        assert float(_value(row1, "shift_hours")) == 0.0, f"预期 OperatorCalendar.raw shift_hours=0，实际 {_value(row1, 'shift_hours')!r}"
        op_cal = cal_svc.get_operator_calendar("OP100", "2026-02-11")
        assert op_cal is not None, "未读取到 OperatorCalendar 记录"
        assert float(op_cal.shift_hours) == 0.0, f"预期 OperatorCalendar.get().shift_hours=0，实际 {op_cal.shift_hours!r}"
        op_policy = cal_svc.policy_for_datetime(datetime(2026, 2, 11, 9, 0, 0), operator_id="OP100")
        assert float(op_policy.shift_hours) == 0.0, f"预期 operator policy.shift_hours=0，实际 {op_policy.shift_hours!r}"

        conn.execute(
            """
            INSERT INTO WorkCalendar (date, day_type, shift_hours, efficiency, allow_normal, allow_urgent, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("2026-02-12", "holiday", -1, 1.0, "no", "no", "legacy negative global"),
        )
        conn.execute(
            """
            INSERT INTO OperatorCalendar (operator_id, date, day_type, shift_hours, efficiency, allow_normal, allow_urgent, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("OP100", "2026-02-13", "holiday", -1, 1.0, "no", "no", "legacy negative operator"),
        )
        conn.commit()

        neg_cal = cal_svc.get("2026-02-12")
        assert float(neg_cal.shift_hours) == 0.0, f"预期历史负工时读侧归零，实际 {neg_cal.shift_hours!r}"
        neg_policy = cal_svc.policy_for_datetime(datetime(2026, 2, 12, 9, 0, 0))
        assert float(neg_policy.shift_hours) == 0.0, f"预期负工时 policy.shift_hours=0，实际 {neg_policy.shift_hours!r}"
        assert capacity_hours(cal_svc, date(2026, 2, 12), date(2026, 2, 12)) == 0.0, "预期负工时读侧归零后 capacity_hours=0"

        neg_op_cal = cal_svc.get_operator_calendar("OP100", "2026-02-13")
        assert neg_op_cal is not None, "未读取到负工时 OperatorCalendar 记录"
        assert float(neg_op_cal.shift_hours) == 0.0, f"预期个人日历负工时读侧归零，实际 {neg_op_cal.shift_hours!r}"
        neg_op_policy = cal_svc.policy_for_datetime(datetime(2026, 2, 13, 9, 0, 0), operator_id="OP100")
        assert float(neg_op_policy.shift_hours) == 0.0, f"预期个人负工时 policy.shift_hours=0，实际 {neg_op_policy.shift_hours!r}"
    finally:
        try:
            conn.close()
        except Exception:
            pass

    print("OK")


if __name__ == "__main__":
    main()
