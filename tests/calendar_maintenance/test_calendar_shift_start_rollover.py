"""回归测试：CalendarService.adjust_to_working_time / add_working_hours 跨天推进时，必须采用下一天自己的 shift_start（如 07:00），不得沿用当天 shift_start，否则会错过次日更早的班次起点。"""

from datetime import date, datetime


def test_calendar_shift_start_rollover(schema_conn) -> None:

    from core.services.scheduler import CalendarService

    conn = schema_conn

    # 两天的工作日历：Day1 08:00 开始，Day2 07:00 开始
    day1 = date(2026, 1, 1).isoformat()
    day2 = date(2026, 1, 2).isoformat()
    conn.execute(
        """
        INSERT INTO WorkCalendar (date, day_type, shift_start, shift_end, shift_hours, efficiency, allow_normal, allow_urgent, remark)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (day1, "workday", "08:00", "16:00", 8.0, 1.0, "yes", "yes", "regression"),
    )
    conn.execute(
        """
        INSERT INTO WorkCalendar (date, day_type, shift_start, shift_end, shift_hours, efficiency, allow_normal, allow_urgent, remark)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (day2, "workday", "07:00", "15:00", 8.0, 1.0, "yes", "yes", "regression"),
    )
    conn.commit()

    cal = CalendarService(conn)

    # 1) adjust_to_working_time：跨天时不应沿用“当天 shift_start”，否则会错过下一天更早的 07:00
    dt_after_shift = datetime(2026, 1, 1, 18, 0, 0)
    adjusted = cal.adjust_to_working_time(dt_after_shift, priority="normal")
    assert adjusted == datetime(2026, 1, 2, 7, 0, 0), f"adjust_to_working_time 跨天错误：{adjusted!r}"

    # 2) add_working_hours：跨天推进应从下一天 07:00 开始（结果应比旧实现提前 1 小时）
    start = datetime(2026, 1, 1, 15, 0, 0)
    end = cal.add_working_hours(start, 2.0, priority="normal")
    assert end == datetime(2026, 1, 2, 8, 0, 0), f"add_working_hours 跨天错误：{end!r}"
