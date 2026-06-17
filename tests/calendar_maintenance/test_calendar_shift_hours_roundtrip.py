"""回归测试：CalendarService 的 shift_hours 在全局 WorkCalendar 与个人 OperatorCalendar 上写入0小时能原样回读（get/policy_for_datetime/capacity_hours 一致为0.0），且历史负工时在读侧不得静默归零、必须抛出指明 shift_hours 字段的 ValueError。"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from typing import Any


def _value(row: Any, key: str):
    if isinstance(row, sqlite3.Row):
        return row[key]
    return row[0]


def test_calendar_shift_hours_roundtrip(db_path) -> None:

    from core.infrastructure.database import ensure_schema, get_connection
    from core.services.report.calculations import capacity_hours
    from core.services.scheduler import CalendarService


    conn = get_connection(db_path)
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

        try:
            cal_svc.get("2026-02-12")
        except ValueError as exc:
            assert "shift_hours" in str(exc), f"负工时错误信息应指出字段：{exc!r}"
        else:
            raise AssertionError("历史负工时读侧不能静默归零")

        try:
            cal_svc.policy_for_datetime(datetime(2026, 2, 12, 9, 0, 0))
        except ValueError as exc:
            assert "shift_hours" in str(exc), f"负工时 policy 错误信息应指出字段：{exc!r}"
        else:
            raise AssertionError("负工时 policy 不能静默归零")

        try:
            capacity_hours(cal_svc, date(2026, 2, 12), date(2026, 2, 12))
        except ValueError as exc:
            assert "shift_hours" in str(exc), f"负工时 capacity 错误信息应指出字段：{exc!r}"
        else:
            raise AssertionError("负工时 capacity 不能静默归零")

        try:
            cal_svc.get_operator_calendar("OP100", "2026-02-13")
        except ValueError as exc:
            assert "shift_hours" in str(exc), f"个人负工时错误信息应指出字段：{exc!r}"
        else:
            raise AssertionError("个人日历负工时读侧不能静默归零")

        try:
            cal_svc.policy_for_datetime(datetime(2026, 2, 13, 9, 0, 0), operator_id="OP100")
        except ValueError as exc:
            assert "shift_hours" in str(exc), f"个人负工时 policy 错误信息应指出字段：{exc!r}"
        else:
            raise AssertionError("个人负工时 policy 不能静默归零")
    finally:
        try:
            conn.close()
        except Exception:
            pass
