"""The calendar migration preserves explicit legacy rows and rejects partial upgrades."""

import pytest

from core.infrastructure.calendar_periods_schema import contract_issues, objects
from core.infrastructure.migrations.v34 import run
from core.services.scheduler.calendar.service import CalendarService


def test_migration_preserves_existing_clock_rows_and_default_absence(schema_conn):
    conn = schema_conn
    CalendarService(conn).upsert("2026-10-05", shift_start="08:00", shift_end="16:00", efficiency=.9)
    expected = dict(conn.execute("SELECT * FROM WorkCalendar").fetchone())
    for name in reversed(list(objects())):
        kind = "TRIGGER" if name.startswith("wb_") else "TABLE"
        conn.execute("DROP " + kind + " " + name)
    for table in ("WorkCalendar", "OperatorCalendar"):
        conn.execute("ALTER TABLE " + table + " DROP COLUMN periods_json")
    conn.commit()
    run(conn)
    assert contract_issues(conn) == []
    assert dict(conn.execute("SELECT * FROM WorkCalendar").fetchone()) == expected
    assert conn.execute("SELECT COUNT(*) FROM WorkbenchCalendarDefaults").fetchone()[0] == 0
    assert CalendarService(conn).get("2026-10-05").periods_json is None
    before = list(conn.iterdump())
    run(conn)
    assert list(conn.iterdump()) == before


def test_partial_period_schema_is_not_silently_repaired(schema_conn):
    schema_conn.execute("DROP TABLE WorkbenchCalendarDefaults")
    schema_conn.commit()
    before = list(schema_conn.iterdump())
    with pytest.raises(RuntimeError, match="partial calendar"):
        run(schema_conn)
    assert list(schema_conn.iterdump()) == before
