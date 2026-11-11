"""Real SQLite calendars for scheduler tests."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from core.services.scheduler.calendar.engine import CalendarEngine
from core.services.workbench.facts.calendar_inputs import calendar_inputs_from_capture
from core.services.workbench.facts.production_capture import ProductionFactsCapture

BASE = datetime(2026, 9, 8, 8)
SCHEMA = (Path(__file__).resolve().parents[2] / "schema.sql").read_text(encoding="utf-8")


def at(hours=0):
    return BASE + timedelta(hours=hours)


def day_row(day=0, **overrides):
    row = dict(
        date=(BASE + timedelta(days=day)).date().isoformat(), day_type="workday",
        efficiency=1.0, allow_normal="yes", allow_urgent="yes", remark="busy-block-test",
        periods_json='[{"start":"08:00","end":"16:00","day_offset":0}]',
    )
    row.update(overrides)
    return row


@contextmanager
def native_calendar(rows=(), operator_rows=()):
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        conn.execute("INSERT INTO Operators (operator_id, name) VALUES ('O1', 'Test operator')")
        days = {day_row(day)["date"]: day_row(day) for day in range(14)}
        days.update({row["date"]: row for row in rows})
        for row in days.values():
            conn.execute(
                "INSERT INTO WorkCalendar (date, day_type, efficiency, allow_normal, allow_urgent, remark, periods_json) "
                "VALUES (:date, :day_type, :efficiency, :allow_normal, :allow_urgent, :remark, :periods_json)", row,
            )
        for row in operator_rows:
            conn.execute(
                "INSERT INTO OperatorCalendar (operator_id, date, day_type, efficiency, allow_normal, allow_urgent, remark, periods_json) "
                "VALUES ('O1', :date, :day_type, :efficiency, :allow_normal, :allow_urgent, :remark, :periods_json)", row,
            )
        conn.commit()
        conn.execute("PRAGMA query_only = ON")
        before = conn.total_changes
        yield CalendarEngine(calendar_inputs_from_capture(ProductionFactsCapture(conn)))
        assert conn.total_changes == before, "Scheduling wrote to the calendar fixture"
    finally:
        conn.close()
