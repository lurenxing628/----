"""Report capacity follows actual shift/window intersections, not midnight samples."""

from datetime import date, datetime
from types import SimpleNamespace

import pytest

from core.services.report.calculations import capacity_hours
from core.services.report.report_engine import ReportEngine
from core.services.scheduler.calendar_service import CalendarService


def _calendar(conn, shifts):
    conn.executemany(
        """INSERT INTO WorkCalendar
        (date, day_type, shift_start, shift_hours, efficiency, allow_normal, allow_urgent)
        VALUES (?, 'workday', ?, ?, ?, 'yes', 'yes')""",
        shifts,
    )
    return CalendarService(conn)


@pytest.mark.parametrize(
    "start_day,end_day,expected",
    [(7, 8, 18.0), (7, 7, 4.0), (8, 8, 14.0)],
)
def test_night_and_next_day_capacity_is_clipped_to_report_dates(schema_conn, start_day, end_day, expected):
    calendar = _calendar(schema_conn, [
        ("2026-09-07", "20:00", 10.0, 1.0),
        ("2026-09-08", "08:00", 8.0, 1.0),
    ])
    assert capacity_hours(calendar, date(2026, 9, start_day), date(2026, 9, end_day)) == expected


@pytest.mark.parametrize(
    "shifts,start_day,end_day,expected",
    [
        ([("2026-09-06", "20:00", 10.0, 1.0)], 7, 7, 14.0),
        ([("2026-09-07", "20:00", 10.0, 0.5), ("2026-09-08", "08:00", 8.0, 1.25)], 7, 8, 15.0),
        ([("2026-09-07", "16:00", 8.0, 1.0)], 7, 8, 16.0),
        ([("2026-09-07", "20:00", 10.0, 1.0), ("2026-09-08", "20:00", 10.0, 1.0)], 7, 8, 14.0),
        ([("2026-09-07", "20:00", 10.0, 1.0), ("2026-09-08", "08:00", 0.0, 1.0)], 8, 8, 6.0),
        ([("2026-09-07", "00:00", 24.0, 1.0)], 7, 7, 24.0),
        ([("2026-09-07", "08:00", 8.0, 1.23456789)], 7, 7, 9.876543),
        ([], 5, 6, 0.0),
        ([], 7, 8, 16.0),
        ([], 8, 7, 0.0),
    ],
    ids=["leading-night", "efficiency", "midnight-end", "two-nights", "night-before-zero",
         "24-hours", "rounding", "weekend", "default-weekdays", "empty-range"],
)
def test_capacity_preserves_calendar_and_range_contracts(schema_conn, shifts, start_day, end_day, expected):
    calendar = _calendar(schema_conn, shifts)
    assert capacity_hours(calendar, date(2026, 9, start_day), date(2026, 9, end_day)) == expected


def test_capacity_does_not_filter_priority_or_use_personal_calendar(schema_conn):
    calendar = _calendar(schema_conn, [("2026-09-07", "08:00", 8.0, 0.5)])
    schema_conn.execute("UPDATE WorkCalendar SET allow_normal='no', allow_urgent='no'")
    schema_conn.execute("INSERT INTO Operators (operator_id, name) VALUES ('O1', 'Operator')")
    schema_conn.execute(
        """INSERT INTO OperatorCalendar
        (operator_id, date, day_type, shift_start, shift_hours, efficiency, allow_normal, allow_urgent)
        VALUES ('O1', '2026-09-07', 'workday', '08:00', 12, 1, 'yes', 'yes')"""
    )
    assert capacity_hours(calendar, date(2026, 9, 7), date(2026, 9, 7)) == 4.0


def test_capacity_calendar_errors_are_not_swallowed(schema_conn, monkeypatch):
    calendar = CalendarService(schema_conn)

    def unavailable(_dt):
        raise RuntimeError("calendar unavailable")

    monkeypatch.setattr(calendar, "policy_for_datetime", unavailable)
    with pytest.raises(RuntimeError, match="calendar unavailable"):
        capacity_hours(calendar, date(2026, 9, 7), date(2026, 9, 8))


@pytest.mark.parametrize("start_day,end_day,expected", [(7, 8, 18.0), (7, 7, 4.0), (8, 8, 14.0)])
@pytest.mark.parametrize("bad_time", [False, True])
def test_report_engine_uses_same_window_for_capacity_and_occupied_hours(schema_conn, monkeypatch, start_day, end_day, expected, bad_time):
    _calendar(schema_conn, [("2026-09-07", "20:00", 10.0, 1.0), ("2026-09-08", "08:00", 8.0, 1.0)])
    engine = ReportEngine(schema_conn)
    resolution = SimpleNamespace(
        selected_role="adopted", requested_role="adopted", scenario_id=None,
        scenario_name=None, is_scenario_preview=False, to_dict=lambda: {},
    )
    monkeypatch.setattr(engine, "_resolve_plan", lambda *args: resolution)
    calls = []

    def rows_between(**kwargs):
        calls.append(kwargs)
        rows = [
            dict(machine_id="M1", operator_id="O1", source="internal", start_time=start, end_time=end)
            for start, end in [
                ("2026-09-07 20:00:00", "2026-09-08 06:00:00"),
                ("2026-09-08 08:00:00", "2026-09-08 16:00:00"),
            ]
        ] + [dict(machine_id="M1", operator_id="O1", source="external",
                  start_time="2026-09-07 00:00:00", end_time="2026-09-09 00:00:00")]
        if bad_time:
            rows.append(dict(machine_id="M1", operator_id="O1", source="internal",
                             start_time="invalid-time", end_time="2026-09-08 11:00:00"))
        return rows

    monkeypatch.setattr(engine, "_list_plan_rows_between", rows_between)
    report = engine.utilization(
        7, date(2026, 9, start_day), date(2026, 9, end_day),
        plan_role="adopted", resource_type="machine", resource_id="M1", batch_id="B1",
    )
    assert report["capacity_hours_per_resource"] == expected
    assert report["report_degraded"] is bad_time
    assert report["report_bad_time_skipped_count"] == int(bad_time)
    for key in ("machines", "operators"):
        assert len(report[key]) == 1
        assert report[key][0]["hours"] == expected
        assert report[key][0]["capacity_hours"] == expected
        assert report[key][0]["utilization"] == 1.0
    assert calls == [dict(
        version=7, plan_role="adopted", scenario_id=None,
        start_time=datetime(2026, 9, start_day).strftime("%Y-%m-%d %H:%M:%S"),
        end_time=datetime(2026, 9, end_day + 1).strftime("%Y-%m-%d %H:%M:%S"),
        resource_type="machine", resource_id="M1", batch_id="B1",
    )]
