"""回归测试：日历读侧归一化——WorkCalendar/OperatorCalendar 存量行混存遗留值（如 day_type=Weekend、allow_normal=Yes/是/NO）时，/scheduler/calendar 与 /personnel/<id>/calendar 页面必须统一渲染成中文口径（假期/是/否），不得把英文或大小写混写原样漏给用户。"""

from __future__ import annotations

import re


def _assert_status(resp, name: str, expect: int = 200) -> None:
    if resp.status_code != expect:
        body = resp.data.decode("utf-8", errors="ignore") if getattr(resp, "data", None) else ""
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect}，body={body[:500]}")


def _assert_calendar_row(
    html: str,
    date_value: str,
    day_type_zh: str,
    shift_hours_re: str,
    allow_normal_zh: str,
    allow_urgent_zh: str,
) -> None:
    pattern = (
        rf"<td>{re.escape(date_value)}</td>"
        rf"\s*<td>{re.escape(day_type_zh)}</td>"
        rf".*?<td>{shift_hours_re}</td>"
        rf".*?<td>{re.escape(allow_normal_zh)}</td>"
        rf"\s*<td>{re.escape(allow_urgent_zh)}</td>"
    )
    if re.search(pattern, html, re.S) is None:
        raise RuntimeError(
            f"未找到归一化后的日历行：date={date_value}, day_type_zh={day_type_zh}, shift_hours_re={shift_hours_re}, "
            f"allow_normal_zh={allow_normal_zh}, allow_urgent_zh={allow_urgent_zh}"
        )


def test_calendar_pages_readside_normalization(app_client, db_path) -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(db_path)
    try:
        conn.execute("INSERT INTO Operators (operator_id, name) VALUES (?, ?)", ("OP100", "测试员甲"))
        conn.execute(
            """
            INSERT INTO WorkCalendar (date, day_type, shift_hours, efficiency, allow_normal, allow_urgent, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("2026-02-01", "Weekend", 0, 1.0, "Yes", "NO", "global legacy"),
        )
        conn.execute(
            """
            INSERT INTO OperatorCalendar (operator_id, date, day_type, shift_hours, efficiency, allow_normal, allow_urgent, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("OP100", "2026-02-02", "Weekend", 0, 1.0, "是", "否", "personal legacy"),
        )
        conn.commit()
    finally:
        conn.close()

    resp_scheduler = app_client.get("/scheduler/calendar")
    _assert_status(resp_scheduler, "GET /scheduler/calendar")
    html_scheduler = resp_scheduler.data.decode("utf-8", errors="ignore")
    _assert_calendar_row(html_scheduler, "2026-02-01", "假期", r"0(?:\.0+)?", "是", "否")

    resp_personnel = app_client.get("/personnel/OP100/calendar")
    _assert_status(resp_personnel, "GET /personnel/OP100/calendar")
    html_personnel = resp_personnel.data.decode("utf-8", errors="ignore")
    _assert_calendar_row(html_personnel, "2026-02-02", "假期", r"0(?:\.0+)?", "是", "否")
