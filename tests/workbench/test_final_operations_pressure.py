"""Actual local windows, duplicate fragments, zero and unknown denominators."""

import pytest

from core.services.workbench.dashboard_resource_metrics import daily_resource_pressure, pressure_summary


def _calendar(start="2026-09-10T08:00:00", end="2026-09-10T16:00:00"):
    return {"state": "available", "windows": [{"start": start, "end": end, "allow_normal": True, "allow_urgent": True}]}


def _task(ref, start, end):
    return {"operation_ref": ref, "start": start, "end": end}


def test_final_operations_pressure_deduplicates_fragments_and_keeps_overlap_separate():
    tasks = [_task("a", "2026-09-10T08:00:00", "2026-09-10T12:00:00"),
             _task("a", "2026-09-10T10:00:00", "2026-09-10T14:00:00"),
             _task("b", "2026-09-10T13:00:00", "2026-09-10T16:00:00")]
    value = daily_resource_pressure(tasks, _calendar(), "2026-09-10T08:00:00", "2026-09-10T16:00:00")
    assert value["peak_utilization"] == 1
    assert value["days"][0]["occupied_hours"] == 8
    assert value["days"][0]["overlap_hours"] == 1
    assert pressure_summary([value])["count"] == 1


def test_final_operations_pressure_clips_overnight_capacity_and_uses_daily_peak():
    calendar = _calendar("2026-09-10T22:00:00", "2026-09-11T06:00:00")
    tasks = [_task("a", "2026-09-10T22:00:00", "2026-09-11T01:00:00")]
    value = daily_resource_pressure(tasks, calendar, "2026-09-10T23:00:00", "2026-09-11T05:00:00")
    assert [row["available_hours"] for row in value["days"]] == [1, 5]
    assert [row["occupied_hours"] for row in value["days"]] == [1, 1]
    assert [row["utilization"] for row in value["days"]] == [1, 0.2]
    assert value["peak_utilization"] == 1


@pytest.mark.parametrize("calendar,expected", [(_calendar(), (0, 0, 0)), ({"state": "available", "windows": []}, (None, 1, 0)),
                                             ({"state": "unavailable", "windows": None}, (None, 0, 1))])
def test_final_operations_pressure_keeps_zero_usage_zero_capacity_unknown_separate(calendar, expected):
    value = daily_resource_pressure([], calendar, "2026-09-10T08:00:00", "2026-09-10T16:00:00")
    assert (value["peak_utilization"], value["zero_capacity_days"], value["unknown_days"]) == expected
    summary = pressure_summary([value])
    assert summary["count"] == (None if expected[2] else 0)


def test_final_operations_pressure_points_do_not_occupy_resources_or_include_right_boundary():
    tasks = [_task("point", "2026-09-10T08:00:00", "2026-09-10T08:00:00"),
             _task("boundary", "2026-09-10T16:00:00", "2026-09-10T17:00:00")]
    value = daily_resource_pressure(tasks, _calendar(), "2026-09-10T08:00:00", "2026-09-10T16:00:00")
    assert value["peak_utilization"] == 0 and value["days"][0]["occupied_hours"] == 0
