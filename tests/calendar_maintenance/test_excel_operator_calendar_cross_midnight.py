"""回归测试：个人工作日历 Excel 行校验器（get_operator_calendar_row_validate_and_normalize）由班次起止时间推导可用工时——跨午夜 22:00->06:00 视为次日结束算 8 小时、相等 08:00->08:00 视为 24 小时整班、正常 08:00->16:00 算 8 小时，并覆盖行内填错的可用工时值。"""

from __future__ import annotations

from typing import Any, Dict


def _assert_float_close(got: Any, expected: float, *, label: str) -> None:
    try:
        v = float(got)
    except Exception:
        raise AssertionError(f"{label}：期望可转为 float（期望值={expected}），实际={got!r}") from None
    if abs(v - float(expected)) > 1e-9:
        raise AssertionError(f"{label}：期望 {expected}，实际 {v}")


def _run_case(validate_row, row: Dict[str, Any], *, expected_hours: float) -> None:
    r = dict(row)
    err = validate_row(r)
    if err:
        raise AssertionError(f"预期校验通过，但返回错误：{err}；row={r!r}")
    _assert_float_close(r.get("可用工时"), expected_hours, label=f"可用工时({r.get('班次开始')}->{r.get('班次结束')})")


def test_excel_operator_calendar_cross_midnight(schema_conn) -> None:

    from core.services.common.excel_validators import get_operator_calendar_row_validate_and_normalize
    from data.repositories import OperatorRepository

    conn = schema_conn

    try:
        conn.execute(
            "INSERT INTO Operators (operator_id, name, status, remark) VALUES (?, ?, ?, ?)",
            ("OP001", "测试员工", "active", ""),
        )
        conn.commit()

        validate_row = get_operator_calendar_row_validate_and_normalize(
            conn,
            holiday_default_efficiency=0.8,
            op_repo=OperatorRepository(conn),
            inplace=True,
        )

        # Case A：跨午夜（22:00 -> 06:00）应视为次日结束，工时=8
        _run_case(
            validate_row,
            {
                "工号": "OP001",
                "日期": "2026-03-01",
                "类型": "workday",
                "班次开始": "22:00",
                "班次结束": "06:00",
                # 故意给一个错误值，确保会被起止时间推导覆盖
                "可用工时": 1,
            },
            expected_hours=8.0,
        )

        # Case B：相等（08:00 -> 08:00）语义为 24h 班次（与 CalendarAdmin/Engine 一致）
        _run_case(
            validate_row,
            {
                "工号": "OP001",
                "日期": "2026-03-02",
                "类型": "workday",
                "班次开始": "08:00",
                "班次结束": "08:00",
            },
            expected_hours=24.0,
        )

        # Case C：正常（08:00 -> 16:00）工时=8
        _run_case(
            validate_row,
            {
                "工号": "OP001",
                "日期": "2026-03-03",
                "类型": "workday",
                "班次开始": "08:00",
                "班次结束": "16:00",
                "可用工时": "0",
            },
            expected_hours=8.0,
        )

    finally:
        try:
            conn.close()
        except Exception:
            pass


