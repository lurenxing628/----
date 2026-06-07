"""回归测试：CalendarService 的 no_tx 写入路径（upsert_no_tx / upsert_operator_calendar_no_tx）须与事务版 upsert 产出一致归一化结果（day_type=workday、allow_*=yes、shift 08:00-16:00），且对负工时、零效率、bool/NaN/inf 等非法 shift_hours 与 efficiency 抛 ValidationError 并保证非法记录不落 WorkCalendar/OperatorCalendar。"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any


def _row_to_dict(row: Any) -> dict:
    if isinstance(row, sqlite3.Row):
        return {k: row[k] for k in row.keys()}
    if isinstance(row, dict):
        return dict(row)
    raise RuntimeError(f"不支持的 row 类型：{type(row)!r}")


def _expect_validation_error(fn, expected_text: str) -> None:
    from core.infrastructure.errors import ValidationError

    try:
        fn()
    except ValidationError as e:
        msg = getattr(e, "message", str(e))
        assert expected_text in msg, f"预期错误包含 {expected_text!r}，实际 {msg!r}"
        return
    raise RuntimeError(f"预期抛出 ValidationError：{expected_text}")


def test_calendar_no_tx_hardening(db_path) -> None:

    from core.infrastructure.database import ensure_schema, get_connection
    from core.services.scheduler import CalendarService


    conn = get_connection(db_path)
    try:
        conn.execute("INSERT INTO Operators (operator_id, name) VALUES (?, ?)", ("OP100", "测试员甲"))
        conn.commit()

        cal_svc = CalendarService(conn, logger=None, op_logger=None)

        def _assert_operator_calendar_write_rejected(
            *,
            date_value: str,
            shift_hours: Any = 8,
            efficiency: Any = 1.0,
            expected_text: str,
        ) -> None:
            _expect_validation_error(
                lambda: cal_svc.upsert_operator_calendar_no_tx(
                    {
                        "operator_id": "OP100",
                        "date": date_value,
                        "day_type": "workday",
                        "shift_hours": shift_hours,
                        "efficiency": efficiency,
                        "allow_normal": "yes",
                        "allow_urgent": "yes",
                    }
                ),
                expected_text,
            )
            cnt = conn.execute("SELECT COUNT(1) FROM OperatorCalendar WHERE operator_id=? AND date=?", ("OP100", date_value)).fetchone()[0]
            assert int(cnt) == 0, f"非法个人日历 no_tx 不应落库，date={date_value} count={cnt}"

        tx_global = cal_svc.upsert(
            "2026-03-10",
            day_type="workday",
            shift_hours=8,
            efficiency=1.0,
            allow_normal="是",
            allow_urgent="是",
            remark="global tx",
        )
        no_tx_global = cal_svc.upsert_no_tx(
            {
                "date": "2026-03-11",
                "day_type": "工作日",
                "shift_hours": 8,
                "efficiency": 1.0,
                "allow_normal": "是",
                "allow_urgent": "是",
                "remark": "global no_tx",
            }
        )
        row_global = conn.execute(
            "SELECT day_type, shift_start, shift_end, shift_hours, efficiency, allow_normal, allow_urgent FROM WorkCalendar WHERE date=?",
            ("2026-03-11",),
        ).fetchone()
        assert row_global is not None, "未写入 WorkCalendar.no_tx 记录"
        row_global_dict = _row_to_dict(row_global)
        assert row_global_dict["day_type"] == "workday", f"预期 no_tx.day_type=workday，实际 {row_global_dict['day_type']!r}"
        assert row_global_dict["allow_normal"] == "yes", f"预期 no_tx.allow_normal=yes，实际 {row_global_dict['allow_normal']!r}"
        assert row_global_dict["allow_urgent"] == "yes", f"预期 no_tx.allow_urgent=yes，实际 {row_global_dict['allow_urgent']!r}"
        assert no_tx_global.day_type == tx_global.day_type == "workday", "事务/非事务 day_type 不一致"
        assert no_tx_global.allow_normal == tx_global.allow_normal == "yes", "事务/非事务 allow_normal 不一致"
        assert no_tx_global.allow_urgent == tx_global.allow_urgent == "yes", "事务/非事务 allow_urgent 不一致"
        assert no_tx_global.shift_start == tx_global.shift_start == "08:00", "事务/非事务 shift_start 不一致"
        assert no_tx_global.shift_end == tx_global.shift_end == "16:00", "事务/非事务 shift_end 不一致"
        policy_tx_global = cal_svc.policy_for_datetime(datetime(2026, 3, 10, 9, 0, 0))
        policy_no_tx_global = cal_svc.policy_for_datetime(datetime(2026, 3, 11, 9, 0, 0))
        assert policy_tx_global.allow_normal == policy_no_tx_global.allow_normal == "yes", "全局日历 policy.allow_normal 不一致"
        assert policy_tx_global.is_priority_allowed("normal") is True, "事务路径 normal 应允许"
        assert policy_no_tx_global.is_priority_allowed("normal") is True, "no_tx 路径 normal 应允许"
        assert policy_tx_global.is_priority_allowed("urgent") is True, "事务路径 urgent 应允许"
        assert policy_no_tx_global.is_priority_allowed("urgent") is True, "no_tx 路径 urgent 应允许"

        tx_operator = cal_svc.upsert_operator_calendar(
            operator_id="OP100",
            date_value="2026-03-12",
            day_type="workday",
            shift_hours=8,
            efficiency=1.0,
            allow_normal="是",
            allow_urgent="是",
            remark="operator tx",
        )
        no_tx_operator = cal_svc.upsert_operator_calendar_no_tx(
            {
                "operator_id": "OP100",
                "date": "2026-03-13",
                "day_type": "工作日",
                "shift_hours": 8,
                "efficiency": 1.0,
                "allow_normal": "是",
                "allow_urgent": "是",
                "remark": "operator no_tx",
            }
        )
        row_operator = conn.execute(
            "SELECT day_type, shift_start, shift_end, shift_hours, efficiency, allow_normal, allow_urgent FROM OperatorCalendar WHERE operator_id=? AND date=?",
            ("OP100", "2026-03-13"),
        ).fetchone()
        assert row_operator is not None, "未写入 OperatorCalendar.no_tx 记录"
        row_operator_dict = _row_to_dict(row_operator)
        assert row_operator_dict["day_type"] == "workday", f"预期 operator no_tx.day_type=workday，实际 {row_operator_dict['day_type']!r}"
        assert row_operator_dict["allow_normal"] == "yes", f"预期 operator no_tx.allow_normal=yes，实际 {row_operator_dict['allow_normal']!r}"
        assert row_operator_dict["allow_urgent"] == "yes", f"预期 operator no_tx.allow_urgent=yes，实际 {row_operator_dict['allow_urgent']!r}"
        assert no_tx_operator.day_type == tx_operator.day_type == "workday", "个人日历事务/非事务 day_type 不一致"
        assert no_tx_operator.allow_normal == tx_operator.allow_normal == "yes", "个人日历事务/非事务 allow_normal 不一致"
        assert no_tx_operator.allow_urgent == tx_operator.allow_urgent == "yes", "个人日历事务/非事务 allow_urgent 不一致"
        assert no_tx_operator.shift_start == tx_operator.shift_start == "08:00", "个人日历事务/非事务 shift_start 不一致"
        assert no_tx_operator.shift_end == tx_operator.shift_end == "16:00", "个人日历事务/非事务 shift_end 不一致"
        policy_tx_operator = cal_svc.policy_for_datetime(datetime(2026, 3, 12, 9, 0, 0), operator_id="OP100")
        policy_no_tx_operator = cal_svc.policy_for_datetime(datetime(2026, 3, 13, 9, 0, 0), operator_id="OP100")
        assert policy_tx_operator.allow_normal == policy_no_tx_operator.allow_normal == "yes", "个人日历 policy.allow_normal 不一致"
        assert policy_tx_operator.is_priority_allowed("normal") is True, "个人事务路径 normal 应允许"
        assert policy_no_tx_operator.is_priority_allowed("normal") is True, "个人 no_tx 路径 normal 应允许"
        assert policy_tx_operator.is_priority_allowed("urgent") is True, "个人事务路径 urgent 应允许"
        assert policy_no_tx_operator.is_priority_allowed("urgent") is True, "个人 no_tx 路径 urgent 应允许"

        _expect_validation_error(
            lambda: cal_svc.upsert_no_tx(
                {
                    "date": "2026-03-14",
                    "day_type": "workday",
                    "shift_hours": -1,
                    "efficiency": 1.0,
                    "allow_normal": "yes",
                    "allow_urgent": "yes",
                }
            ),
            "可用工时",
        )
        cnt_global_neg = conn.execute("SELECT COUNT(1) FROM WorkCalendar WHERE date=?", ("2026-03-14",)).fetchone()[0]
        assert int(cnt_global_neg) == 0, f"负工时 no_tx 不应落库，实际 count={cnt_global_neg}"

        _expect_validation_error(
            lambda: cal_svc.upsert_no_tx(
                {
                    "date": "2026-03-15",
                    "day_type": "workday",
                    "shift_hours": 8,
                    "efficiency": 0,
                    "allow_normal": "yes",
                    "allow_urgent": "yes",
                }
            ),
            "效率",
        )
        cnt_global_eff = conn.execute("SELECT COUNT(1) FROM WorkCalendar WHERE date=?", ("2026-03-15",)).fetchone()[0]
        assert int(cnt_global_eff) == 0, f"零效率 no_tx 不应落库，实际 count={cnt_global_eff}"

        _expect_validation_error(
            lambda: cal_svc.upsert_operator_calendar_no_tx(
                {
                    "operator_id": "OP100",
                    "date": "2026-03-16",
                    "day_type": "workday",
                    "shift_hours": -1,
                    "efficiency": 1.0,
                    "allow_normal": "yes",
                    "allow_urgent": "yes",
                }
            ),
            "可用工时",
        )
        cnt_operator_neg = conn.execute(
            "SELECT COUNT(1) FROM OperatorCalendar WHERE operator_id=? AND date=?",
            ("OP100", "2026-03-16"),
        ).fetchone()[0]
        assert int(cnt_operator_neg) == 0, f"个人负工时 no_tx 不应落库，实际 count={cnt_operator_neg}"

        _expect_validation_error(
            lambda: cal_svc.upsert_operator_calendar_no_tx(
                {
                    "operator_id": "OP100",
                    "date": "2026-03-17",
                    "day_type": "workday",
                    "shift_hours": 8,
                    "efficiency": 0,
                    "allow_normal": "yes",
                    "allow_urgent": "yes",
                }
            ),
            "效率",
        )
        cnt_operator_eff = conn.execute(
            "SELECT COUNT(1) FROM OperatorCalendar WHERE operator_id=? AND date=?",
            ("OP100", "2026-03-17"),
        ).fetchone()[0]
        assert int(cnt_operator_eff) == 0, f"个人零效率 no_tx 不应落库，实际 count={cnt_operator_eff}"

        for idx, value in enumerate((True, False, float("nan"), float("inf"), float("-inf")), start=18):
            _assert_operator_calendar_write_rejected(
                date_value=f"2026-03-{idx:02d}",
                shift_hours=value,
                expected_text="必须是数字" if isinstance(value, bool) else "必须是有限数字",
            )

        for idx, value in enumerate((True, False, float("nan"), float("inf"), float("-inf")), start=23):
            _assert_operator_calendar_write_rejected(
                date_value=f"2026-03-{idx:02d}",
                efficiency=value,
                expected_text="必须是数字" if isinstance(value, bool) else "必须是有限数字",
            )
    finally:
        try:
            conn.close()
        except Exception:
            pass


