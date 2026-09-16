"""Report capacity follows actual shift/window intersections, not midnight samples."""

from datetime import date, datetime
from types import SimpleNamespace

import pytest

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


@pytest.mark.parametrize("start_day,end_day,expected", [(7, 8, 18.0), (7, 7, 4.0), (8, 8, 14.0)])
@pytest.mark.parametrize("bad_time", [False, True])
def test_report_engine_uses_same_window_for_capacity_and_occupied_hours(schema_conn, monkeypatch, start_day, end_day, expected, bad_time):
    _calendar(schema_conn, [("2026-09-07", "20:00", 10.0, 1.0), ("2026-09-08", "08:00", 8.0, 1.0)])
    schema_conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('M1','Machine')")
    schema_conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator')")
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
