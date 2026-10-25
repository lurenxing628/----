"""Downtime reports keep touching windows, task multiplicity and source diagnostics."""

import itertools
from datetime import datetime, timedelta

import pytest

from core.services.capacity.plan_calendar_intervals import IntervalIndex
from core.services.report.downtime_impact import compute_downtime_impact
from core.services.report.report_degradation import (
    record_report_bad_time_row,
    record_report_missing_machine_row,
    report_degradation_payload,
)
from core.services.report.utilization import group_utilization_rows, utilization_from_groups
from core.services.report.utilization_calendars import (
    _project_resources,
    resource_calendars_for_ids,
    resource_ids_from_groups,
)
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
    assert collector.to_counters() == {}
    payload = report_degradation_payload(collector)
    assert payload == {"report_degraded": False}


def test_report_degradation_payload_only_marks_corrupted_or_incomplete_inputs_degraded():
    clean = DegradationCollector()
    assert report_degradation_payload(clean) == {"report_degraded": False}

    bad_time = DegradationCollector()
    record_report_bad_time_row(bad_time, scope="schedule")
    assert report_degradation_payload(bad_time)["report_degraded"] is True

    missing_machine = DegradationCollector()
    record_report_missing_machine_row(
        missing_machine,
        scope="downtime",
    )
    assert report_degradation_payload(missing_machine)["report_degraded"] is True

    unknown_capacity = DegradationCollector()
    unknown_capacity.add(
        code="resource_load_capacity_failed",
        scope="resource_load",
        field="占用率",
        message="日历资料不完整",
    )
    assert report_degradation_payload(unknown_capacity)["report_degraded"] is True


def test_downtime_overlap_clips_to_query_window_and_zero_duration_point_events_do_not_degrade():
    collector = DegradationCollector()
    start_dt = datetime(2026, 10, 17, 0, 0)
    end_dt_excl = datetime(2026, 10, 18, 0, 0)

    downtime_rows = [
        {
            "machine_id": "M1",
            "machine_name": "M1",
            "start_time": "2026-10-16T20:00:00",
            "end_time": "2026-10-17T04:00:00",
        }
    ]
    schedule_rows = [
        {
            "op_id": 1,
            "machine_id": "M1",
            "machine_name": "M1",
            "operator_id": "OP1",
            "operator_name": "OP1",
            "start_time": "2026-10-16T22:00:00",
            "end_time": "2026-10-17T02:00:00",
            "source": "internal",
        },
        {
            "op_id": 2,
            "machine_id": "M1",
            "machine_name": "M1",
            "operator_id": "OP1",
            "operator_name": "OP1",
            "start_time": "2026-10-17T01:00:00",
            "end_time": "2026-10-17T01:00:00",
            "source": "internal",
        },
    ]

    impact = compute_downtime_impact(
        downtime_rows=downtime_rows,
        schedule_rows=schedule_rows,
        start_dt=start_dt,
        end_dt_excl=end_dt_excl,
        degradation_collector=collector,
    )
    assert impact == [
        {
            "machine_id": "M1",
            "machine_name": "M1",
            "downtime_hours": 4.0,
            "downtime_count": 1,
            "schedule_overlap_hours": 2.0,
            "schedule_overlap_count": 1,
        }
    ]

    calendar_projection = {
        "state": "available",
        "windows": [
            {
                "start": "2026-10-17 00:00:00",
                "end": "2026-10-17 08:00:00",
                "allow_normal": True,
                "allow_urgent": True,
            }
        ],
        "issues": [],
    }
    calendars = {
        ("machine", "M1"): calendar_projection,
        ("operator", "OP1"): calendar_projection,
    }
    groups = group_utilization_rows(schedule_rows, start_dt, end_dt_excl, collector)
    machines, operators = utilization_from_groups(
        groups,
        start_dt=start_dt,
        end_dt_excl=end_dt_excl,
        calendars=calendars,
        degradation_collector=collector,
    )
    assert len(machines) == 1 and machines[0]["hours"] == 2.0 and machines[0]["task_count"] == 1
    assert len(operators) == 1 and operators[0]["hours"] == 2.0 and operators[0]["task_count"] == 1
    assert collector.to_counters() == {}
    payload = report_degradation_payload(collector)
    assert payload == {"report_degraded": False}


def test_report_preserves_raw_resource_id_without_stripping_non_empty_whitespace():
    collector = DegradationCollector()
    start_dt = datetime(2026, 10, 17, 0, 0)
    end_dt_excl = datetime(2026, 10, 18, 0, 0)
    schedule_rows = [
        {
            "op_id": 1,
            "machine_id": " M1 ",
            "machine_name": "设备一",
            "operator_id": " OP1 ",
            "operator_name": "人员一",
            "start_time": "2026-10-17T08:00:00",
            "end_time": "2026-10-17T10:00:00",
            "source": "internal",
        },
        {
            "op_id": 2,
            "machine_id": "   ",
            "operator_id": "   ",
            "start_time": "2026-10-17T08:00:00",
            "end_time": "2026-10-17T10:00:00",
            "source": "internal",
        },
    ]
    downtime_rows = [
        {
            "machine_id": " M1 ",
            "machine_name": "设备一",
            "start_time": "2026-10-17T09:00:00",
            "end_time": "2026-10-17T11:00:00",
        }
    ]
    groups = group_utilization_rows(schedule_rows, start_dt, end_dt_excl, collector)
    ids = resource_ids_from_groups(groups)
    assert ids == {"machine": [" M1 "], "operator": [" OP1 "]}

    facts = {
        "defaults": (),
        "legacy_defaults": True,
        "global": [
            {
                "date": "2026-10-17",
                "day_type": "workday",
                "shift_start": "08:00",
                "shift_end": "16:00",
                "shift_hours": 8.0,
                "periods_json": None,
                "efficiency": 1.0,
                "allow_normal": "yes",
                "allow_urgent": "yes",
                "remark": None,
            }
        ],
        "personal": [
            {
                "operator_id": " OP1 ",
                "date": "2026-10-17",
                "day_type": "workday",
                "shift_start": "08:00",
                "shift_end": "14:00",
                "shift_hours": 6.0,
                "periods_json": None,
                "efficiency": 1.0,
                "allow_normal": "yes",
                "allow_urgent": "yes",
                "remark": None,
            }
        ],
        "profiles": [],
        "patterns": [],
        "machines": [{"machine_id": " M1 ", "status": "active"}],
        "operators": [{"operator_id": " OP1 ", "status": "active"}],
        "downtimes": [],
    }
    calendars = _project_resources(
        ids,
        facts,
        start_dt.date() - timedelta(days=1),
        start_dt.date(),
        start_dt,
        end_dt_excl,
    )
    machines, operators = utilization_from_groups(
        groups,
        start_dt=start_dt,
        end_dt_excl=end_dt_excl,
        calendars=calendars,
        degradation_collector=collector,
    )
    assert [row["machine_id"] for row in machines] == [" M1 "]
    assert machines[0]["capacity_hours"] == 8.0
    assert [row["operator_id"] for row in operators] == [" OP1 "]
    assert operators[0]["capacity_hours"] == 6.0

    impact = compute_downtime_impact(
        downtime_rows=downtime_rows,
        schedule_rows=schedule_rows,
        start_dt=start_dt,
        end_dt_excl=end_dt_excl,
        degradation_collector=collector,
    )
    assert impact == [
        {
            "machine_id": " M1 ",
            "machine_name": "设备一",
            "downtime_hours": 2.0,
            "downtime_count": 1,
            "schedule_overlap_hours": 1.0,
            "schedule_overlap_count": 1,
        }
    ]
    assert collector.to_counters() == {}


def test_resource_calendars_only_project_resources_occupying_the_report_window(schema_conn):
    conn = schema_conn
    conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','turning')")
    conn.execute("INSERT INTO Machines(machine_id,name,op_type_id,status) VALUES ('M1','lathe','T1','active')")
    conn.execute("INSERT INTO Operators(operator_id,name,status) VALUES ('OP1','operator','active')")
    conn.commit()
    start_dt, end_dt_excl = datetime(2026, 10, 1), datetime(2026, 11, 1)

    op_ids = itertools.count(1)

    def row(key, start, end, source="internal"):
        return {"op_id": next(op_ids), "machine_id": key, "machine_name": key, "operator_id": key.replace("M", "OP"), "operator_name": key,
                "start_time": start, "end_time": end, "source": source}

    schedule_rows = [row("M1", "2026-10-17T08:00:00", "2026-10-17T10:00:00"),
                     row("M-OUTSIDE", "2026-11-03T08:00:00", "2026-11-03T10:00:00"),
                     row("M-BAD", "not a time", "2026-10-17T10:00:00"),
                     row("M-REVERSED", "2026-10-17T10:00:00", "2026-10-17T08:00:00"),
                     row("M-EXTERNAL", "2026-10-17T08:00:00", "2026-10-17T10:00:00", source="external")]
    # 700 个点事件各带一台设备一个人：若也投影日历，32 天 ×(1+1400) 个单元格会超过 40000 的预算。
    schedule_rows += [row(f"M-POINT-{index}", "2026-10-17T08:00:00", "2026-10-17T08:00:00") for index in range(700)]
    # 与报表引擎同一条链路：一次分组同时决定日历投影范围和占用率。
    collector = DegradationCollector()
    groups = group_utilization_rows(schedule_rows, start_dt, end_dt_excl, collector)
    calendars = resource_calendars_for_ids(conn, resource_ids_from_groups(groups), start_dt, end_dt_excl)
    assert set(calendars) == {("machine", "M1"), ("operator", "OP1")}
    assert all(item["state"] == "available" for item in calendars.values())
    machines, operators = utilization_from_groups(groups, start_dt=start_dt, end_dt_excl=end_dt_excl,
                                                  calendars=calendars, degradation_collector=collector)
    assert [item["machine_id"] for item in machines] == ["M1"] and [item["operator_id"] for item in operators] == ["OP1"]
    assert machines[0]["capacity_hours"] is not None and operators[0]["capacity_hours"] is not None
    # 日历预算和占用率共用同一次分组，坏时间只报一次。
    assert collector.to_counters() == {"bad_time_row_skipped": 2}
