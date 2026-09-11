"""日历旧 GET 明确退役；保留的导出读侧归一为中文且不改写全局或个人原值。"""

from __future__ import annotations

from tests._support.legacy_http import assert_retired_response, xlsx_download_rows
from tests._support.sqlite_snapshot import table_rows


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
        before = {table: table_rows(conn, table) for table in ("WorkCalendar", "OperatorCalendar")}
    finally:
        conn.close()

    assert_retired_response(app_client.get("/scheduler/calendar"))
    assert_retired_response(app_client.get("/personnel/OP100/calendar"))
    global_rows = xlsx_download_rows(app_client.get("/scheduler/excel/calendar/export"))
    personal_rows = xlsx_download_rows(app_client.get("/personnel/excel/operator_calendar/export"))
    assert len(global_rows) == len(personal_rows) == 1
    assert global_rows[0]["日期"] == "2026-02-01"
    assert personal_rows[0]["日期"] == "2026-02-02" and personal_rows[0]["工号"] == "OP100"
    for row in (global_rows[0], personal_rows[0]):
        assert row["类型"] == "假期"
        assert row["可用工时"] == 0
        assert row["允许普通件"] == "是" and row["允许急件"] == "否"
    conn = get_connection(db_path)
    try:
        assert before == {table: table_rows(conn, table) for table in before}
    finally:
        conn.close()
