"""回归测试：全局日历 /scheduler/excel/calendar/export 与个人日历 /personnel/excel/operator_calendar/export 导出时，将库内遗留的 Weekend/YES/NO 等枚举与 YesNo 值规范化为中文展示（类型=假期、允许普通件=是、允许急件=否），且可被 normalize_calendar_day_type_value / normalize_yes_no_narrow_value 反解回 HOLIDAY/YES/NO。"""

from __future__ import annotations

import io
from typing import Any, Dict, List, Optional


def _assert_status(resp, name: str, expect: int = 200) -> None:
    if resp.status_code != expect:
        body = resp.data.decode("utf-8", errors="ignore") if getattr(resp, "data", None) else ""
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect}，body={body[:500]}")


def _sheet_rows(resp_bytes: bytes) -> List[Dict[str, Any]]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(resp_bytes))
    ws = wb.active
    assert ws is not None

    rows = list(ws.iter_rows(values_only=True))
    headers = [str(x) if x is not None else "" for x in rows[0]]
    out: List[Dict[str, Any]] = []
    for row in rows[1:]:
        item: Dict[str, Any] = {}
        for i, key in enumerate(headers):
            value = row[i]
            if hasattr(value, "isoformat"):
                try:
                    value = value.isoformat()
                except Exception:
                    pass
            item[key] = value
        out.append(item)
    return out


def _find_row(rows: List[Dict[str, Any]], **conditions: Any) -> Optional[Dict[str, Any]]:
    for row in rows:
        if all(row.get(k) == v for k, v in conditions.items()):
            return row
    return None


def test_calendar_export_normalization(app_client, db_path) -> None:
    from core.infrastructure.database import get_connection
    from core.models.enums import CalendarDayType, YesNo
    from core.services.common.normalization_matrix import (
        normalize_calendar_day_type_value,
        normalize_yes_no_narrow_value,
    )

    conn = get_connection(db_path)
    try:
        conn.execute("INSERT INTO Operators (operator_id, name) VALUES (?, ?)", ("OP100", "测试员甲"))
        conn.execute(
            """
            INSERT INTO WorkCalendar (date, day_type, shift_hours, efficiency, allow_normal, allow_urgent, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("2026-02-01", "Weekend", 0, 1.0, "是", "NO", "global legacy"),
        )
        conn.execute(
            """
            INSERT INTO OperatorCalendar (operator_id, date, day_type, shift_hours, efficiency, allow_normal, allow_urgent, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("OP100", "2026-02-02", "Weekend", 0, 1.0, "YES", "否", "personal legacy"),
        )
        conn.commit()
    finally:
        conn.close()

    resp_global = app_client.get("/scheduler/excel/calendar/export")
    _assert_status(resp_global, "GET /scheduler/excel/calendar/export")
    global_rows = _sheet_rows(resp_global.data)
    global_row = _find_row(global_rows, 日期="2026-02-01")
    if global_row is None:
        raise RuntimeError(f"未找到全局日历导出行：{global_rows!r}")
    assert global_row["类型"] == "假期", f"预期全局导出 类型=假期，实际 {global_row['类型']!r}"
    assert global_row["允许普通件"] == "是", f"预期全局导出 允许普通件=是，实际 {global_row['允许普通件']!r}"
    assert global_row["允许急件"] == "否", f"预期全局导出 允许急件=否，实际 {global_row['允许急件']!r}"
    assert normalize_calendar_day_type_value(global_row["类型"]) == CalendarDayType.HOLIDAY.value
    assert normalize_yes_no_narrow_value(global_row["允许普通件"]) == YesNo.YES.value
    assert normalize_yes_no_narrow_value(global_row["允许急件"]) == YesNo.NO.value

    resp_operator = app_client.get("/personnel/excel/operator_calendar/export")
    _assert_status(resp_operator, "GET /personnel/excel/operator_calendar/export")
    operator_rows = _sheet_rows(resp_operator.data)
    operator_row = _find_row(operator_rows, 工号="OP100", 日期="2026-02-02")
    if operator_row is None:
        raise RuntimeError(f"未找到个人日历导出行：{operator_rows!r}")
    assert operator_row["类型"] == "假期", f"预期个人导出 类型=假期，实际 {operator_row['类型']!r}"
    assert operator_row["允许普通件"] == "是", f"预期个人导出 允许普通件=是，实际 {operator_row['允许普通件']!r}"
    assert operator_row["允许急件"] == "否", f"预期个人导出 允许急件=否，实际 {operator_row['允许急件']!r}"
    assert normalize_calendar_day_type_value(operator_row["类型"]) == CalendarDayType.HOLIDAY.value
    assert normalize_yes_no_narrow_value(operator_row["允许普通件"]) == YesNo.YES.value
    assert normalize_yes_no_narrow_value(operator_row["允许急件"]) == YesNo.NO.value
