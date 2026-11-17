"""Downtime reports keep touching windows, task multiplicity and source diagnostics."""

import itertools
from datetime import datetime, timedelta

import pytest

from core.models.workbench_report import ReportPage
from core.models.workbench_report_catalog import ReportCatalogScope
from core.services.capacity.plan_calendar_intervals import IntervalIndex
from core.services.common.plan_query import SchedulePlanQueryService
from core.services.report.downtime_impact import compute_downtime_impact
from core.services.report.report_engine import ReportEngine
from core.services.report.utilization import group_utilization_rows, utilization_from_groups
from core.services.report.utilization_calendars import (
    _project_resources,
    resource_calendars_for_ids,
    resource_ids_from_groups,
)
from core.services.workbench.report.catalog import catalog_workspace
from core.shared.degradation import DegradationCollector
from core.shared.local_datetime import datetime_to_us
from tests.workbench.execution_ledger_support import publish_official_plan


def _us(text):
    return datetime_to_us(datetime.fromisoformat(text))


def _downtime(machine, start, end, name=None):
    """A stored active downtime row as MachineDowntimeRepository returns it."""
    return {"machine_id": machine, "machine_name": machine if name is None else name,
            "start_us": _us(start), "end_us": _us(end)}


def _times(start, end):
    """Stored Schedule instants as the plan detail query returns them."""
    start_us, end_us = _us(start), _us(end)
    return {"start_us": start_us, "end_us": end_us, "is_point_event": int(start_us == end_us)}


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
    downtime = _downtime

    def task(machine, start, end, source="internal"):
        return {"machine_id": machine, "source": source, **_times(start, end)}

    day = "2026-10-17T"
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
    )
    assert result == [
        {"machine_id": "M2", "machine_name": "M2", "downtime_hours": 3.0, "downtime_count": 2,
         "schedule_overlap_hours": 1.0, "schedule_overlap_count": 1},
        {"machine_id": "M1", "machine_name": "M1", "downtime_hours": 2.0, "downtime_count": 2,
         "schedule_overlap_hours": 3.0, "schedule_overlap_count": 4},
        {"machine_id": "M3", "machine_name": "M3", "downtime_hours": 1.0, "downtime_count": 1,
         "schedule_overlap_hours": 0.0, "schedule_overlap_count": 0},
    ]


def test_utilization_report_is_degraded_exactly_when_resource_capacity_cannot_be_computed(schema_conn):
    conn = schema_conn
    conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','turning')")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','part')")
    conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B1','P1',1)")
    rows = []
    # 320 台设备、320 名人员：62 天的报表窗口要投影 63 天 ×(1+640) 格，超过日历投影上限 40000 格，容量算不出来。
    for index in range(320):
        machine, operator = f"M{index:03d}", f"O{index:03d}"
        conn.execute("INSERT INTO Machines(machine_id,name) VALUES (?,?)", (machine, machine))
        conn.execute("INSERT INTO Operators(operator_id,name) VALUES (?,?)", (operator, operator))
        op_id = conn.execute(
            "INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source) "
            "VALUES (?,'B1',?,'T1','turning','internal')", (f"OP{index:03d}", index + 1)).lastrowid
        rows.append({"op_id": op_id, "machine_id": machine, "operator_id": operator,
                     "start_time": "2026-09-09T08:00:00", "end_time": "2026-09-09T09:00:00"})
    publish_official_plan(conn, 1, rows)
    engine = ReportEngine(conn)
    resolution = SchedulePlanQueryService(conn).resolve_existing_plan(1)

    day = engine.utilization(resolution, "2026-09-09", "2026-09-09")
    assert day["report_degraded"] is False
    assert all(row["capacity_hours"] is not None for row in day["machines"] + day["operators"])

    window = engine.utilization(resolution, "2026-09-01", "2026-11-01")
    assert window["report_degraded"] is True
    assert len(window["machines"]) == len(window["operators"]) == 320
    assert all(row["capacity_hours"] is None for row in window["machines"] + window["operators"])


def test_downtime_overlap_clips_to_query_window_and_zero_duration_point_events_do_not_degrade():
    collector = DegradationCollector()
    start_dt = datetime(2026, 10, 17, 0, 0)
    end_dt_excl = datetime(2026, 10, 18, 0, 0)

    downtime_rows = [_downtime("M1", "2026-10-16T20:00:00", "2026-10-17T04:00:00")]
    schedule_rows = [
        {
            "op_id": 1,
            "machine_id": "M1",
            "machine_name": "M1",
            "operator_id": "OP1",
            "operator_name": "OP1",
            **_times("2026-10-16T22:00:00", "2026-10-17T02:00:00"),
            "source": "internal",
        },
        {
            "op_id": 2,
            "machine_id": "M1",
            "machine_name": "M1",
            "operator_id": "OP1",
            "operator_name": "OP1",
            **_times("2026-10-17T01:00:00", "2026-10-17T01:00:00"),
            "source": "internal",
        },
    ]

    impact = compute_downtime_impact(
        downtime_rows=downtime_rows,
        schedule_rows=schedule_rows,
        start_dt=start_dt,
        end_dt_excl=end_dt_excl,
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
                "start": datetime(2026, 10, 17, 0, 0),
                "end": datetime(2026, 10, 17, 8, 0),
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
    groups = group_utilization_rows(schedule_rows, start_dt, end_dt_excl)
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
            **_times("2026-10-17T08:00:00", "2026-10-17T10:00:00"),
            "source": "internal",
        },
    ]
    downtime_rows = [_downtime(" M1 ", "2026-10-17T09:00:00", "2026-10-17T11:00:00", "设备一")]
    groups = group_utilization_rows(schedule_rows, start_dt, end_dt_excl)
    ids = resource_ids_from_groups(groups)
    assert ids == {"machine": [" M1 "], "operator": [" OP1 "]}

    facts = {
        "defaults": (),
        "global": [
            {
                "date": "2026-10-17",
                "day_type": "workday",
                "periods_json": '[{"start":"08:00","end":"16:00","day_offset":0}]',
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
                "periods_json": '[{"start":"08:00","end":"14:00","day_offset":0}]',
                "efficiency": 1.0,
                "allow_normal": "yes",
                "allow_urgent": "yes",
                "remark": None,
            }
        ],
        "profiles": [],
        "shift_profiles": [],
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
    conn.execute("INSERT INTO Machines(machine_id,name,status) VALUES ('M1','lathe','active')")
    conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES ('M1','T1')")
    conn.execute("INSERT INTO Operators(operator_id,name,status) VALUES ('OP1','operator','active')")
    conn.commit()
    start_dt, end_dt_excl = datetime(2026, 10, 1), datetime(2026, 11, 1)

    op_ids = itertools.count(1)

    def row(key, start, end, source="internal"):
        return {"op_id": next(op_ids), "machine_id": key, "machine_name": key, "operator_id": key.replace("M", "OP"), "operator_name": key,
                "source": source, **_times(start, end)}

    schedule_rows = [row("M1", "2026-10-17T08:00:00", "2026-10-17T10:00:00"),
                     row("M-OUTSIDE", "2026-11-03T08:00:00", "2026-11-03T10:00:00"),
                     row("M-EXTERNAL", "2026-10-17T08:00:00", "2026-10-17T10:00:00", source="external")]
    # 700 个点事件各带一台设备一个人：若也投影日历，32 天 ×(1+1400) 个单元格会超过 40000 的预算。
    schedule_rows += [row(f"M-POINT-{index}", "2026-10-17T08:00:00", "2026-10-17T08:00:00") for index in range(700)]
    # 与报表引擎同一条链路：一次分组同时决定日历投影范围和占用率。
    collector = DegradationCollector()
    groups = group_utilization_rows(schedule_rows, start_dt, end_dt_excl)
    calendars = resource_calendars_for_ids(conn, resource_ids_from_groups(groups), start_dt, end_dt_excl)
    assert set(calendars) == {("machine", "M1"), ("operator", "OP1")}
    assert all(item["state"] == "available" for item in calendars.values())
    machines, operators = utilization_from_groups(groups, start_dt=start_dt, end_dt_excl=end_dt_excl,
                                                  calendars=calendars, degradation_collector=collector)
    assert [item["machine_id"] for item in machines] == ["M1"] and [item["operator_id"] for item in operators] == ["OP1"]
    assert machines[0]["capacity_hours"] is not None and operators[0]["capacity_hours"] is not None


def test_catalog_search_matches_rows_only_reachable_through_zero_values():
    def machine(key, name, hours, count):
        return {"machine_id": key, "machine_name": name, "downtime_hours": hours, "downtime_count": count,
                "schedule_overlap_hours": hours, "schedule_overlap_count": count}

    facts = {"scope": ReportCatalogScope("downtime", query="0"), "plan": {}, "identities": {
                 "machine": {"M-IDLE": {"ref": "a" * 48}, "M-BUSY": {"ref": "b" * 48}}},
             "report": {"machines": [machine("M-IDLE", "idle", 0.0, 0), machine("M-BUSY", "busy", 1.5, 2)], "operators": []}}
    data, ordered, selected = catalog_workspace(facts, ReportPage(sort="resource_label"), as_of=datetime(2026, 10, 17))
    assert [row["resource_label"] for row in data["rows"]] == ["idle"]
    assert selected == []
    _, _, selected = catalog_workspace(
        facts, ReportPage(sort="resource_label"), as_of=datetime(2026, 10, 17), include_sources=True
    )
    assert [row["machine_id"] for row in selected] == ["M-IDLE"]


def test_global_calendar_is_built_lazily_zero_times_for_overridden_operators_and_once_when_shared(monkeypatch):
    from core.services.capacity import plan_calendar_windows

    start_dt = datetime(2026, 10, 17, 0, 0)
    end_dt_excl = datetime(2026, 10, 18, 0, 0)
    first_day = start_dt.date() - timedelta(days=1)
    last_day = start_dt.date()

    calls = []
    real_projection = plan_calendar_windows.policy_projection

    def tracked_projection(engine, first, last, start, end, operator_id=None):
        calls.append(operator_id)
        return real_projection(engine, first, last, start, end, operator_id)

    monkeypatch.setattr(plan_calendar_windows, "policy_projection", tracked_projection)

    def personal_row(who, day_str, end_clock="14:00"):
        return {
            "operator_id": who,
            "date": day_str,
            "day_type": "workday",
            "periods_json": f'[{{"start":"08:00","end":"{end_clock}","day_offset":0}}]',
            "efficiency": 1.0,
            "allow_normal": "yes",
            "allow_urgent": "yes",
            "remark": None,
        }

    broken_global = [
        {
            "date": "2026-10-17",
            "day_type": "workday",
            "periods_json": "broken-global-periods",
            "efficiency": 1.0,
            "allow_normal": "yes",
            "allow_urgent": "yes",
            "remark": None,
        }
    ]
    overridden_facts = {
        "defaults": (),
        "global": broken_global,
        "personal": [
            personal_row("OP1", "2026-10-16"),
            personal_row("OP1", "2026-10-17"),
        ],
        "profiles": [],
        "shift_profiles": [],
        "patterns": [],
        "machines": [],
        "operators": [{"operator_id": "OP1", "status": "active"}],
        "downtimes": [],
    }
    projected = _project_resources(
        {"machine": ["M-MISSING"], "operator": ["OP1"]},
        overridden_facts,
        first_day,
        last_day,
        start_dt,
        end_dt_excl,
    )
    assert calls == ["OP1"]
    assert projected["operator", "OP1"]["state"] == "available"
    assert projected["operator", "OP1"]["available_hours"] == 6.0
    assert projected["machine", "M-MISSING"]["issues"][0]["code"] == "resource_missing"

    calls.clear()
    valid_global = [
        {
            "date": "2026-10-17",
            "day_type": "workday",
            "periods_json": '[{"start":"08:00","end":"16:00","day_offset":0}]',
            "efficiency": 1.0,
            "allow_normal": "yes",
            "allow_urgent": "yes",
            "remark": None,
        }
    ]
    shared_facts = {
        "defaults": (),
        "global": valid_global,
        "personal": [
            personal_row("OP1", "2026-10-16"),
            personal_row("OP1", "2026-10-17"),
        ],
        "profiles": [],
        "shift_profiles": [],
        "patterns": [],
        "machines": [
            {"machine_id": "M1", "status": "active"},
            {"machine_id": "M2", "status": "active"},
        ],
        "operators": [
            {"operator_id": "OP1", "status": "active"},
            {"operator_id": "OP2", "status": "active"},
            {"operator_id": "OP3", "status": "active"},
        ],
        "downtimes": [],
    }
    shared = _project_resources(
        {"machine": ["M1", "M2"], "operator": ["OP1", "OP2", "OP3"]},
        shared_facts,
        first_day,
        last_day,
        start_dt,
        end_dt_excl,
    )
    assert calls.count(None) == 1
    assert calls == [None, "OP1"]
    assert shared["machine", "M1"]["available_hours"] == 8.0
    assert shared["operator", "OP2"]["available_hours"] == 8.0
    assert shared["operator", "OP3"]["available_hours"] == 8.0

    # 全局日历损坏时，多个继承全局的人员与设备依然只构建 1 次全局投影，不二次重扫全局。
    calls.clear()
    broken_shared = _project_resources(
        {"machine": ["M1"], "operator": ["OP2", "OP3"]},
        {**shared_facts, "global": broken_global, "personal": []},
        first_day,
        last_day,
        start_dt,
        end_dt_excl,
    )
    assert calls == [None]
    assert broken_shared["machine", "M1"]["state"] == "unavailable"
    assert broken_shared["operator", "OP2"]["state"] == "unavailable"
    assert broken_shared["operator", "OP2"]["basis"] == "personal_or_operator_shift_calendar"

    # ArchivedCalendar._resource_day 同样在计算 _policy_day 前通过 resource_record_unavailable 短路缺失的资源。
    from core.services.workbench.facts.archived_calendar import ArchivedCalendar

    m_missing_ref, o_missing_ref = "a" * 48, "b" * 48
    saved_tables = {
        "SchemaVersion": [{"id": 1, "version": 45}],
        "WorkbenchEntityRefs": [
            {"kind": "machine", "ref": m_missing_ref, "entity_key": "M-GONE", "active": 1},
            {"kind": "operator", "ref": o_missing_ref, "entity_key": "OP-GONE", "active": 1},
        ],
        "Machines": [],
        "Operators": [],
        "WorkCalendar": broken_global,
        "OperatorCalendar": [],
        "MachineDowntimes": [],
        "WorkbenchOperatorProfiles": [],
        "WorkbenchShiftProfiles": [],
        "WorkbenchShiftPatternDays": [],
        "WorkbenchCalendarDefaults": [],
    }
    calls.clear()
    archived_results = dict(
        ArchivedCalendar(saved_tables).iter_resources(
            [
                {"kind": "machine", "ref": m_missing_ref, "saved_id": "M-GONE"},
                {"kind": "operator", "ref": o_missing_ref, "saved_id": "OP-GONE"},
            ],
            "2026-10-17T00:00:00",
            "2026-10-18T00:00:00",
        )
    )
    assert calls == []
    assert archived_results[m_missing_ref]["issues"][0]["code"] == "resource_missing"
    assert archived_results[o_missing_ref]["issues"][0]["code"] == "resource_missing"
