"""Downtime reports keep touching windows, task multiplicity and source diagnostics."""

from datetime import datetime, timedelta

import pytest

from core.services.capacity.plan_calendar_intervals import IntervalIndex
from core.services.report.downtime_impact import compute_downtime_impact
from core.shared.degradation import DegradationCollector


def test_interval_overlap_keeps_touching_windows_and_subsecond_boundaries():
    origin = datetime(2026, 10, 17)

    def at(seconds):
        return origin + timedelta(seconds=seconds)

    index = IntervalIndex.from_normalized([(at(0), at(2)), (at(2), at(4)), (at(7), at(9))])
    cases = [(-2, 0, 0.0, 0), (0, 2, 2.0, 1), (1, 3, 2.0, 2), (4, 7, 0.0, 0),
             (2, 8, 3.0, 2), (-10, 20, 6.0, 3), (1.999999, 2.000001, 0.000002, 2),
             (9, 12, 0.0, 0), (3, 3, 0.0, 0)]
    for start, end, seconds, count in cases:
        actual_seconds, actual_count = index.seconds_and_count_between(at(start), at(end))
        assert actual_seconds == pytest.approx(seconds, abs=1e-12)
        assert actual_count == count
    assert IntervalIndex.from_normalized([]).seconds_and_count_between(at(0), at(2)) == (0.0, 0)


def test_downtime_report_keeps_raw_count_merge_diagnostics_and_overlapping_tasks():
    def downtime(machine, start, end):
        return {"machine_id": machine, "machine_name": machine, "start_time": start, "end_time": end}

    def task(machine, start, end, source="internal"):
        return {"machine_id": machine, "start_time": start, "end_time": end, "source": source}

    day = "2026-10-17T"
    collector = DegradationCollector()
    result = compute_downtime_impact(
        downtime_rows=[downtime("M1", day + "08:00:00", day + "09:00:00"),
                       downtime("M1", day + "09:00:00", day + "10:00:00"),
                       downtime("M2", day + "08:00:00", day + "10:00:00"),
                       downtime("M2", day + "09:00:00", day + "11:00:00"),
                       downtime("M3", day + "08:00:00", day + "09:00:00")],
        schedule_rows=[task("M1", day + "07:00:00", day + "08:00:00"),
                       task("M1", day + "08:00:00", day + "10:00:00"),
                       task("M1", day + "08:30:00", day + "09:30:00"),
                       task("M1", day + "10:00:00", day + "11:00:00"),
                       task("M1", day + "08:00:00", day + "10:00:00", source="external"),
                       task("M2", day + "08:30:00", day + "09:30:00")],
        start_dt=datetime(2026, 10, 17, 7), end_dt_excl=datetime(2026, 10, 17, 12),
        degradation_collector=collector,
    )
    assert result == [
        {"machine_id": "M2", "machine_name": "M2", "downtime_hours": 3.0, "downtime_count": 2,
         "schedule_overlap_hours": 1.0, "schedule_overlap_count": 1},
        {"machine_id": "M1", "machine_name": "M1", "downtime_hours": 2.0, "downtime_count": 2,
         "schedule_overlap_hours": 3.0, "schedule_overlap_count": 4},
        {"machine_id": "M3", "machine_name": "M3", "downtime_hours": 1.0, "downtime_count": 1,
         "schedule_overlap_hours": 0.0, "schedule_overlap_count": 0},
    ]
    assert collector.to_counters() == {"downtime_overlap_merged": 1}
