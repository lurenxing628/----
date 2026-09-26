"""Lossless schedule instants across readers, SQLite predicates and delivery."""

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_scope import local_time
from core.services.capacity.plan_calendar_intervals import public_intervals
from core.services.common.overdue_calculations import parse_dt as overdue_parse
from core.services.report.calculation_helpers import parse_dt as report_parse
from core.services.scheduler._sched_display_utils import fmt_dt, parse_dt
from core.services.scheduler.gantt.critical_chain import _parse_dt as gantt_parse
from core.services.scheduler.schedule_service import ScheduleService
from core.services.workbench.plan.delivery_projection import project_delivery_batch, task_intervals
from core.shared.local_datetime import parse_local_datetime
from data.repositories.schedule_time_sql import parse_dt_for_sql, register_schedule_time_sql_functions

PARSERS = (parse_local_datetime, overdue_parse, report_parse, parse_dt, gantt_parse, ScheduleService._normalize_datetime)


@pytest.mark.parametrize("text", ["2026-09-09 08:00:10.8", "2026-09-09T08:00:10.800000", "2026/09/09 08：00：10.800000"])
def test_schedule_readers_retain_same_instant(text):
    expected = datetime(2026, 9, 9, 8, 0, 10, 800000)
    assert all(parse(text) == expected for parse in PARSERS)
    assert fmt_dt(expected) == parse_dt_for_sql(text) == "2026-09-09 08:00:10.800000"
    assert fmt_dt(expected.replace(microsecond=0)) == "2026-09-09 08:00:10"


@pytest.mark.parametrize("value", ["2026-02-30 08:00:00.123456", "2026-09-09 24:00:00", "2026-09-09T08:00:00Z",
    "2026-09-09T08:00:00+08:00", "2026-09-09T08:00:00.1234567", float("inf"), float("nan"),
    datetime(2026, 9, 9, 8, tzinfo=timezone.utc), b"2026-09-09 08:00:00"])
def test_bad_or_nonlocal_times_are_not_rounded_or_coerced(value):
    assert all(parse(value) is None for parse in PARSERS)
    assert parse_dt_for_sql(value) is None


def test_sql_comparison_preserves_touching_microsecond_boundaries():
    with sqlite3.connect(":memory:") as conn:
        register_schedule_time_sql_functions(conn)
        values = ("2026-09-09T08:00:00.000001", "2026-09-09 08:00:00.000002", "2026-09-09 08:00:00.000003")
        assert conn.execute("SELECT aps_parse_dt(?) < aps_parse_dt(?), aps_parse_dt(?) < aps_parse_dt(?)",
                            (values[0], values[1], values[1], values[2])).fetchone() == (1, 1)
        assert conn.execute("SELECT aps_parse_dt(?) = aps_parse_dt(?)", (values[0], values[0])).fetchone() == (1,)
        assert conn.execute("SELECT aps_parse_dt(?) = aps_parse_dt(?)", ("2026-09-09 08:00:00.000000", "2026-09-09 08:00:00")).fetchone() == (1,)


@pytest.mark.parametrize("finish,risk", [("2026-09-09T23:59:59.999999", "on_time"),
    ("2026-09-10T00:00:00", "overdue"), ("2026-09-10T00:00:00.000001", "overdue")])
@pytest.mark.parametrize("label", [None, "Part"])
def test_delivery_retains_finish_and_day_boundary_even_without_historical_label(finish, risk, label):
    batch = {"batch_id": "B1", "part_no": "P1", "part_name": label, "due_date": "2026-09-09"}
    rows = [{"schedule_id": 1, "op_id": 1, "start_time": "2026-09-09T23:59:58.999999", "end_time": finish}]
    item = project_delivery_batch(batch, "1" * 48, rows, [{"op_id": 1}], task_intervals(rows), False, [])
    assert item["risk"] == risk and item["planned_finish"] == finish
    assert item["schedule_complete"] and item["invalid_task_count"] == 0
    assert ("part_label_missing" in item["issues"]) == (label is None)


def test_calendar_wire_does_not_extend_or_shorten_occupancy():
    start = datetime(2026, 9, 9, 8, 0, 0, 123456)
    end = start + timedelta(microseconds=1)
    assert public_intervals([(start, end)]) == [{"start": start.isoformat(), "end": end.isoformat()}]


def test_public_scope_accepts_its_own_lossless_output():
    assert local_time("2026-09-09T08:00:00.123456") == "2026-09-09T08:00:00.123456"
    for value in ("2026-09-09T08:00:00.1", "2026-09-09T08:00:00.000000", "2026-09-09 08:00:00.123456"):
        with pytest.raises(WorkbenchCommandRejected):
            local_time(value)


def test_downtime_overlap_remains_positive_at_microsecond_boundaries():
    from core.services.workbench.dashboard.downtime import _overlaps

    low = datetime(2026, 9, 9, 8, 0, 0, 123456)
    high = low + timedelta(microseconds=1)
    windows = [(low.replace(microsecond=0), high.replace(microsecond=0) + timedelta(seconds=1),
                {"id": 1, "reason_detail": "Registered downtime"})]
    overlap, = _overlaps(windows, {1: {"ref": "1" * 48}}, low, high)
    assert overlap["overlap_start"] == low.isoformat()
    assert overlap["overlap_end"] == high.isoformat()
    assert overlap["overlap_start"] < overlap["overlap_end"]


@pytest.mark.parametrize("start,end,expected", [
    (datetime(2026, 9, 9, 8, 0, 0, 1), datetime(2026, 9, 9, 8, 1), 0),
    (datetime(2026, 9, 9, 8, 1), datetime(2026, 9, 9, 8, 0, 0, 1), -1),
    (datetime(1, 1, 1, microsecond=1), datetime(9999, 1, 1), 5258439359),
])
def test_critical_chain_minute_floor_keeps_microseconds(start, end, expected):
    from core.services.scheduler.gantt.critical_chain import _minutes_between

    assert _minutes_between(start, end) == expected
