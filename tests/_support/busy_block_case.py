"""Real SQLite calendars for scheduler tests."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from core.services.scheduler.calendar.service import CalendarService

BASE = datetime(2026, 9, 8, 8)
SCHEMA = (Path(__file__).resolve().parents[2] / "schema.sql").read_text(encoding="utf-8")


def at(hours=0):
    return BASE + timedelta(hours=hours)


def day_row(day=0, **overrides):
    row = dict(
        date=(BASE + timedelta(days=day)).date().isoformat(), day_type="workday",
        shift_start="08:00", shift_end="16:00", shift_hours=8.0,
        efficiency=1.0, allow_normal="yes", allow_urgent="yes", remark="busy-block-test",
    )
    row.update(overrides)
    return row


@contextmanager
def native_calendar(rows=(), operator_rows=(), calendar_type=CalendarService):
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        conn.execute("INSERT INTO Operators (operator_id, name) VALUES ('O1', 'Test operator')")
        days = {day_row(day)["date"]: day_row(day) for day in range(14)}
        days.update({row["date"]: row for row in rows})
        for row in days.values():
            conn.execute(
                "INSERT INTO WorkCalendar (date, day_type, shift_start, shift_end, shift_hours, "
                "efficiency, allow_normal, allow_urgent, remark) VALUES "
                "(:date, :day_type, :shift_start, :shift_end, :shift_hours, :efficiency, "
                ":allow_normal, :allow_urgent, :remark)", row,
            )
        for row in operator_rows:
            conn.execute(
                "INSERT INTO OperatorCalendar (operator_id, date, day_type, shift_start, shift_end, "
                "shift_hours, efficiency, allow_normal, allow_urgent, remark) VALUES "
                "('O1', :date, :day_type, :shift_start, :shift_end, :shift_hours, :efficiency, "
                ":allow_normal, :allow_urgent, :remark)", row,
            )
        conn.commit()
        conn.execute("PRAGMA query_only = ON")
        before = conn.total_changes
        yield calendar_type(conn)
        assert conn.total_changes == before, "Scheduling wrote to the calendar fixture"
    finally:
        conn.close()
